"""LangGraph-based agent for multi-hop reasoning and complex query handling."""
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from enum import Enum
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from core.llm_client import OllamaClient
from tools.tool_registry import ToolRegistry

logger = logging.getLogger("crawllama")


class ReasoningState(TypedDict):
    """State for the reasoning graph."""
    query: str
    context: Annotated[List[str], operator.add]
    current_step: int
    max_steps: int
    needs_more_info: bool
    answer: Optional[str]
    search_queries: Annotated[List[str], operator.add]
    confidence: float
    reasoning_path: Annotated[List[str], operator.add]


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

    def __init__(
        self,
        config: Dict[str, Any],
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
        self.max_hops = max_hops
        self.confidence_threshold = confidence_threshold
        self.enable_critique = enable_critique

        # Initialize LLM client
        llm_config = config.get("llm", {})
        self.llm = OllamaClient(
            base_url=llm_config.get("base_url", "http://127.0.0.1:11434"),
            model=llm_config.get("model", "qwen2.5:3b"),
            temperature=llm_config.get("temperature", 0.7)
        )

        # Initialize tool registry
        rag_config = config.get("rag", {})
        self.tool_registry = ToolRegistry(
            rag_enabled=rag_config.get("enabled", True),
            config=config
        )

        # Build reasoning graph
        self.graph = self._build_graph()

        logger.info(f"Multi-hop agent initialized (max_hops={max_hops}, critique={enable_critique})")

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
        logger.info(f"Router: analyzing query complexity")

        # Analyze query complexity
        complexity_prompt = f"""Analysiere diese Frage: "{query}"

Ist diese Frage:
1. EINFACH - direkt beantwortbar
2. KOMPLEX - benötigt mehrere Schritte oder Vergleiche

Antworte nur mit "EINFACH" oder "KOMPLEX"."""

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
            search_result = web_search.func(query, max_results=5)
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
        context = "\n\n".join(state["context"])

        logger.info(f"Analyzing information (step {state['current_step']})")

        # Generate analysis
        analysis_prompt = f"""Frage: {query}

Verfügbare Informationen:
{context}

Analysiere:
1. Kann die Frage mit diesen Informationen vollständig beantwortet werden?
2. Welche Informationen fehlen noch?
3. Bewerte dein Vertrauen (0-100%)

Antworte im Format:
VOLLSTÄNDIG: JA/NEIN
FEHLENDE_INFO: [was fehlt]
VERTRAUEN: [0-100]"""

        analysis = self.llm.generate(analysis_prompt)
        state["reasoning_path"].append(f"Analysis: {analysis[:200]}...")

        # Parse analysis
        is_complete = "JA" in analysis.split("VOLLSTÄNDIG:")[1].split("\n")[0] if "VOLLSTÄNDIG:" in analysis else False

        # Extract confidence
        try:
            confidence_str = analysis.split("VERTRAUEN:")[1].split("\n")[0].strip()
            confidence = float(''.join(filter(str.isdigit, confidence_str))) / 100.0
        except:
            confidence = 0.5

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

        followup_prompt = f"""Ursprüngliche Frage: {state['query']}

Bisherige Informationen:
{context}

Generiere eine spezifische Folge-Suchanfrage, um fehlende Informationen zu finden.
Antworte nur mit der Suchanfrage."""

        followup_query = self.llm.generate(followup_prompt).strip()

        # Perform follow-up search
        tools = self.tool_registry.get_tools()
        web_search = next((t for t in tools if t.name == "web_search"), None)

        if web_search and followup_query:
            search_result = web_search.func(followup_query, max_results=3)
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
        context = "\n\n".join(state["context"])

        synthesis_prompt = f"""Frage: {query}

Gesammelte Informationen aus {len(state['search_queries'])} Suchen:
{context}

Synthesiere eine umfassende, präzise Antwort auf die ursprüngliche Frage.
Nutze alle verfügbaren Informationen und strukturiere die Antwort klar.
Zitiere relevante Quellen."""

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

        critique_prompt = f"""Frage: {state['query']}

Generierte Antwort:
{state['answer']}

Kritische Bewertung:
1. Beantwortet die Antwort die Frage vollständig? (JA/NEIN)
2. Sind die Informationen korrekt und konsistent?
3. Fehlen wichtige Aspekte?
4. Qualitätsscore (0-100)

Antworte im Format:
VOLLSTÄNDIG: JA/NEIN
QUALITÄT: [0-100]
VERBESSERUNG: [was fehlt]"""

        critique = self.llm.generate(critique_prompt)

        # Parse critique
        is_good = "JA" in critique.split("VOLLSTÄNDIG:")[1].split("\n")[0] if "VOLLSTÄNDIG:" in critique else True

        try:
            quality_str = critique.split("QUALITÄT:")[1].split("\n")[0].strip()
            quality = float(''.join(filter(str.isdigit, quality_str))) / 100.0
        except:
            quality = state["confidence"]

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

    def query(self, user_query: str) -> Dict[str, Any]:
        """
        Process query with multi-hop reasoning.

        Args:
            user_query: User's question

        Returns:
            Dictionary with answer, reasoning path, and metadata
        """
        logger.info(f"Multi-hop query: '{user_query}'")

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
