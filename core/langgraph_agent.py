"""LangGraph-based agent for multi-hop reasoning and complex query handling."""
import logging
from enum import Enum
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from core.cloud_llm_client import create_llm_client_from_config
from core.model_registry import get_model_context_window
from tools.tool_registry import ToolRegistry
from utils.text_cleaner import get_text_cleaner

logger = logging.getLogger("crawllama")


class ReasoningState(TypedDict):
    """State for the reasoning graph.

    NOTE: deliberately no ``Annotated[..., operator.add]`` reducers. The nodes
    append to these lists in place and return the FULL state; with an
    add-reducer LangGraph would concatenate the returned (already-updated)
    list back onto the channel, duplicating context/queries/path on every hop.
    """
    query: str
    context: list[str]
    current_step: int
    max_steps: int
    needs_more_info: bool
    answer: str | None
    search_queries: list[str]
    confidence: float
    reasoning_path: list[str]


def _parse_marker_flag(text: str, marker: str, default: bool) -> bool:
    """Read a YES/NO marker line (``MARKER: YES``) from LLM output."""
    if marker not in text:
        return default
    return "YES" in text.split(marker)[1].split("\n")[0]


def _parse_marker_score(text: str, marker: str, default: float) -> float:
    """Read a 0-100 score line (``MARKER: 85``) from LLM output as 0.0-1.0."""
    try:
        raw = text.split(marker)[1].split("\n")[0].strip()
        return float(''.join(filter(str.isdigit, raw))) / 100.0
    except Exception:
        return default


class NodeType(str, Enum):
    """Types of reasoning nodes."""
    ROUTER = "router"
    INITIAL_SEARCH = "initial_search"
    ANALYZE = "analyze"
    FOLLOW_UP = "follow_up"
    SYNTHESIZE = "synthesize"
    CRITIQUE = "critique"
    END = "end"


class MultiHopReasoningAgent:
    """Agent with multi-hop reasoning capabilities using LangGraph."""

    # Hard ceiling on reasoning hops. Each hop fires a live web search plus a
    # full synthesis pass, so an unbounded (client-supplied) value is a
    # resource/cost amplification vector. Requests above this are clamped.
    MAX_HOPS_CEILING = 10

    def __init__(
        self,
        config: dict[str, Any],
        max_hops: int = 3,
        confidence_threshold: float = 0.7,
        enable_critique: bool = True
    ):
        """
        Initialize multi-hop reasoning agent.

        Args:
            config: Configuration dictionary
            max_hops: Maximum number of reasoning hops
            confidence_threshold: Minimum confidence to stop reasoning
            enable_critique: Enable self-critique loop
        """
        self.config = config
        # Clamp to a sane range to bound cost regardless of caller input.
        self.max_hops = max(1, min(int(max_hops), self.MAX_HOPS_CEILING))
        if self.max_hops != max_hops:
            logger.warning(
                "max_hops=%s clamped to %d (allowed range 1-%d)",
                max_hops, self.max_hops, self.MAX_HOPS_CEILING,
            )
        self.confidence_threshold = confidence_threshold
        self.enable_critique = enable_critique

        llm_config = config.get("llm", {})
        self.provider = llm_config.get("provider", "ollama")
        safe_llm_max_tokens = self._init_llm_client(llm_config)

        rag_config = config.get("rag", {})
        self.tool_registry = ToolRegistry(
            rag_enabled=rag_config.get("enabled", True),
            config=config
        )

        self.graph = self._build_graph()
        self.max_context_tokens = self._compute_context_budget(safe_llm_max_tokens)

        logger.info("Multi-hop agent initialized (max_hops=%s, critique=%s)", max_hops, enable_critique)  # lgtm[py/log-injection] - parameterized logging; false positive

    def _init_llm_client(self, llm_config: dict[str, Any]) -> int:
        """Create the LLM client and set context window/text cleaner.

        Returns the generation token budget, clamped to the model's
        context window.
        """
        model_name = llm_config.get("model", "qwen2.5:3b")
        configured_max_tokens = llm_config.get("max_tokens", 4096)
        context_window_override = llm_config.get("context_window", 0)
        self.context_window = get_model_context_window(
            model_name,
            self.provider,
            context_window_override if context_window_override > 0 else None,
        )
        safe_llm_max_tokens = min(
            configured_max_tokens,
            max(64, self.context_window - 512),
            self.context_window,
        )
        if safe_llm_max_tokens < configured_max_tokens:
            logger.warning(
                "Configured llm.max_tokens=%d exceeds safe generation budget for model window=%d. "
                "Using %d instead.",
                configured_max_tokens,
                self.context_window,
                safe_llm_max_tokens,
            )
        self.text_cleaner = get_text_cleaner(model_name)

        self.llm = create_llm_client_from_config(
            llm_config,
            model=model_name,
            max_tokens=safe_llm_max_tokens,
            context_window=self.context_window,
        )
        return safe_llm_max_tokens

    def _compute_context_budget(self, safe_llm_max_tokens: int) -> int:
        """Compute the max prompt-context tokens, reserving room for the response."""
        response_tokens = min(
            safe_llm_max_tokens,
            max(256, self.context_window // 5),
            self.context_window,
        )
        if response_tokens >= self.context_window:
            response_tokens = max(64, self.context_window // 4)
        # Reserve room for prompt framing and question text
        prompt_overhead = 200
        return max(0, self.context_window - response_tokens - prompt_overhead)

    def _truncate_context(self, context_items: list, max_tokens: int | None = None) -> str:
        """
        Intelligently truncate context to fit within token limits.
        
        Always respects the configured context budget.
        
        Args:
            context_items: List of context strings
            max_tokens: Maximum tokens (defaults to max_context_tokens)
            
        Returns:
            Truncated context string
        """
        full_context = "\n\n".join(context_items)
        max_tokens = max_tokens if max_tokens is not None else self.max_context_tokens

        if self.text_cleaner.estimate_tokens(full_context) <= max_tokens:
            return full_context

        truncated = self.text_cleaner.truncate_by_tokens(full_context, max_tokens)
        logger.info(
            "Context truncated to fit budget: tokens=%d",
            max_tokens,
        )
        return truncated

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow for multi-hop reasoning.

        Returns:
            Compiled StateGraph
        """
        workflow = StateGraph(ReasoningState)

        # Add nodes
        workflow.add_node(NodeType.ROUTER, self._router_node)
        workflow.add_node(NodeType.INITIAL_SEARCH, self._initial_search_node)
        workflow.add_node(NodeType.ANALYZE, self._analyze_node)
        workflow.add_node(NodeType.FOLLOW_UP, self._follow_up_node)
        workflow.add_node(NodeType.SYNTHESIZE, self._synthesize_node)

        if self.enable_critique:
            workflow.add_node(NodeType.CRITIQUE, self._critique_node)

        # Define edges
        workflow.set_entry_point(NodeType.ROUTER)

        # Router decides: simple query -> initial_search, complex -> initial_search
        workflow.add_edge(NodeType.ROUTER, NodeType.INITIAL_SEARCH)

        # Initial search -> analyze
        workflow.add_edge(NodeType.INITIAL_SEARCH, NodeType.ANALYZE)

        # Analyze decides: needs_more_info -> follow_up, else -> synthesize
        workflow.add_conditional_edges(
            NodeType.ANALYZE,
            self._should_continue_search,
            {
                "continue": NodeType.FOLLOW_UP,
                "synthesize": NodeType.SYNTHESIZE
            }
        )

        # Follow-up -> analyze (loop for multi-hop)
        workflow.add_edge(NodeType.FOLLOW_UP, NodeType.ANALYZE)

        # Synthesize -> critique or end
        if self.enable_critique:
            workflow.add_edge(NodeType.SYNTHESIZE, NodeType.CRITIQUE)

            # Critique decides: good -> END, needs_improvement -> follow_up
            workflow.add_conditional_edges(
                NodeType.CRITIQUE,
                self._should_improve,
                {
                    "improve": NodeType.FOLLOW_UP,
                    "end": END
                }
            )
        else:
            workflow.add_edge(NodeType.SYNTHESIZE, END)

        return workflow.compile()

    def _router_node(self, state: ReasoningState) -> ReasoningState:
        """
        Route query to appropriate processing path.

        Args:
            state: Current reasoning state

        Returns:
            Updated state
        """
        query = state["query"]
        logger.info("Router: analyzing query complexity")

        # Analyze query complexity
        complexity_prompt = f"""Analyze this question: "{query}"

Is this question:
1. SIMPLE - directly answerable
2. COMPLEX - requires multiple steps or comparisons

Respond only with "SIMPLE" or "COMPLEX"."""

        complexity = self.llm.generate(complexity_prompt).strip().upper()

        state["reasoning_path"].append(f"Router: Query classified as {complexity}")
        state["current_step"] = 0

        return state

    def _initial_search_node(self, state: ReasoningState) -> ReasoningState:
        """
        Perform initial information search.

        Args:
            state: Current reasoning state

        Returns:
            Updated state with search results
        """
        query = state["query"]
        logger.info(f"Initial search for: {query}")

        # Get web search tool
        tools = self.tool_registry.get_tools()
        web_search = next((t for t in tools if t.name == "web_search"), None)

        if web_search:
            search_result = web_search.func(query)  # Fixed: removed max_results parameter
            state["context"].append(f"Initial search: {search_result}")
            state["search_queries"].append(query)
        else:
            state["context"].append("Initial search: No web search tool available")

        state["current_step"] += 1
        state["reasoning_path"].append(f"Step {state['current_step']}: Initial search completed")

        return state

    def _analyze_node(self, state: ReasoningState) -> ReasoningState:
        """
        Analyze gathered information and decide if more info is needed.

        Args:
            state: Current reasoning state

        Returns:
            Updated state with analysis
        """
        query = state["query"]
        # Truncate context to prevent token limit errors
        context = self._truncate_context(state["context"])

        logger.info(f"Analyzing information (step {state['current_step']})")

        # Generate analysis
        analysis_prompt = f"""Question: {query}

Available information:
{context}

Analyze:
1. Can the question be fully answered with this information?
2. What information is still missing?
3. Rate your confidence (0-100%)

Respond in format:
COMPLETE: YES/NO
MISSING_INFO: [what's missing]
CONFIDENCE: [0-100]"""

        analysis = self.llm.generate(analysis_prompt)
        state["reasoning_path"].append(f"Analysis: {analysis[:200]}...")

        # Parse analysis. SECURITY/cost: if the model's COMPLETE marker is
        # missing/unparseable, fail safe toward STOPPING rather than burning
        # another hop (each hop is a live search + synthesis).
        if "COMPLETE:" not in analysis:
            logger.warning("Analysis missing COMPLETE marker; stopping to bound cost")
        is_complete = _parse_marker_flag(analysis, "COMPLETE:", default=True)
        confidence = _parse_marker_score(analysis, "CONFIDENCE:", default=0.5)

        state["confidence"] = confidence
        state["needs_more_info"] = not is_complete and state["current_step"] < state["max_steps"]

        logger.info(f"Analysis complete: complete={is_complete}, confidence={confidence:.2f}")

        return state

    def _should_continue_search(self, state: ReasoningState) -> str:
        """
        Decide if more information gathering is needed.

        Args:
            state: Current reasoning state

        Returns:
            Next node: "continue" or "synthesize"
        """
        if state["needs_more_info"] and state["current_step"] < state["max_steps"]:
            return "continue"
        return "synthesize"

    def _follow_up_node(self, state: ReasoningState) -> ReasoningState:
        """
        Perform follow-up search based on missing information.

        Args:
            state: Current reasoning state

        Returns:
            Updated state with additional information
        """
        logger.info(f"Follow-up search (step {state['current_step']})")

        # Generate follow-up query
        context = "\n".join(state["context"][-2:])  # Last 2 context items

        followup_prompt = f"""Original question: {state['query']}

Previous information:
{context}

Generate a specific follow-up search query to find missing information.
Respond only with the search query."""

        followup_query = self.llm.generate(followup_prompt).strip()

        # Perform follow-up search
        tools = self.tool_registry.get_tools()
        web_search = next((t for t in tools if t.name == "web_search"), None)

        if web_search and followup_query:
            search_result = web_search.func(followup_query)  # Fixed: removed max_results parameter
            state["context"].append(f"Follow-up search: {search_result}")
            state["search_queries"].append(followup_query)

        state["current_step"] += 1
        state["reasoning_path"].append(f"Step {state['current_step']}: Follow-up search for '{followup_query[:50]}...'")

        return state

    def _synthesize_node(self, state: ReasoningState) -> ReasoningState:
        """
        Synthesize final answer from all gathered information.

        Args:
            state: Current reasoning state

        Returns:
            Updated state with final answer
        """
        logger.info("Synthesizing final answer")

        query = state["query"]
        # Intelligently truncate context to prevent token limit errors
        context = self._truncate_context(state["context"])

        synthesis_prompt = f"""Question: {query}

Collected information from {len(state['search_queries'])} searches:
{context}

Synthesize a comprehensive, precise answer to the original question.
Use all available information and structure the answer clearly.
Cite relevant sources."""

        answer = self.llm.generate(synthesis_prompt)
        state["answer"] = answer

        state["reasoning_path"].append(f"Synthesis: Generated answer ({len(answer)} chars)")

        return state

    def _critique_node(self, state: ReasoningState) -> ReasoningState:
        """
        Self-critique the generated answer.

        Args:
            state: Current reasoning state

        Returns:
            Updated state with critique
        """
        logger.info("Critiquing answer")

        critique_prompt = f"""Question: {state['query']}

Generated answer:
{state['answer']}

Critical evaluation:
1. Does the answer fully address the question? (YES/NO)
2. Is the information correct and consistent?
3. Are important aspects missing?
4. Quality score (0-100)

Respond in format:
COMPLETE: YES/NO
QUALITY: [0-100]
IMPROVEMENT: [what's missing]"""

        critique = self.llm.generate(critique_prompt)

        # Parse critique
        is_good = _parse_marker_flag(critique, "COMPLETE:", default=True)
        quality = _parse_marker_score(critique, "QUALITY:", default=state["confidence"])

        state["confidence"] = quality
        state["needs_more_info"] = not is_good and state["current_step"] < state["max_steps"]

        state["reasoning_path"].append(f"Critique: Quality={quality:.2f}, Complete={is_good}")

        return state

    def _should_improve(self, state: ReasoningState) -> str:
        """
        Decide if answer needs improvement.

        Args:
            state: Current reasoning state

        Returns:
            Next node: "improve" or "end"
        """
        if (state["confidence"] < self.confidence_threshold and
            state["current_step"] < state["max_steps"] and
            state.get("needs_more_info", False)):
            return "improve"
        return "end"

    def query(self, user_query: str) -> dict[str, Any]:
        """
        Process query with multi-hop reasoning.

        Args:
            user_query: User's question

        Returns:
            Dictionary with answer, reasoning path, and metadata
        """
        logger.info("Multi-hop query: '%s'", user_query)  # lgtm[py/log-injection] - parameterized logging; false positive

        # Initialize state
        initial_state: ReasoningState = {
            "query": user_query,
            "context": [],
            "current_step": 0,
            "max_steps": self.max_hops,
            "needs_more_info": True,
            "answer": None,
            "search_queries": [],
            "confidence": 0.0,
            "reasoning_path": []
        }

        # Run graph
        try:
            final_state = self.graph.invoke(initial_state)

            return {
                "answer": final_state.get("answer", "No answer generated"),
                "confidence": final_state.get("confidence", 0.0),
                "steps": final_state.get("current_step", 0),
                "search_queries": final_state.get("search_queries", []),
                "reasoning_path": final_state.get("reasoning_path", [])
            }

        except Exception as e:
            logger.error(f"Multi-hop reasoning failed: {e}")
            return {
                "answer": f"Error during reasoning: {str(e)}",
                "confidence": 0.0,
                "steps": 0,
                "search_queries": [],
                "reasoning_path": [f"Error: {str(e)}"]
            }


# Standard tuning shared by every entry point (CLI and API) so they reason
# identically. Change here, not in the callers.
DEFAULT_MAX_HOPS = 3
DEFAULT_CONFIDENCE_THRESHOLD = 0.7


def create_multihop_agent(config: dict[str, Any]) -> MultiHopReasoningAgent:
    """Build a multi-hop agent with the standard defaults."""
    return MultiHopReasoningAgent(
        config=config,
        max_hops=DEFAULT_MAX_HOPS,
        confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD,
    )
