"""Plugin driver — deterministic, offline load → invoke → unload.

Drives the real :class:`core.plugin_manager.PluginManager` through its full
security-gated load path (allowlist + sha256 verification) against the committed
fixture plugin ``plugins/example_plugin.py``. An enabling config with the plugin's
real sha256 is written into the scenario workdir; the plugin is discovered,
loaded, its tool invoked, then unloaded. No network.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from arena.drivers.base import Driver, DriverContext, DriverResult
from core import telemetry


class PluginDriver(Driver):
    name = "plugin"

    def run(self, scenario_input: dict[str, Any], context: DriverContext) -> DriverResult:
        from core.plugin_manager import PluginManager

        plugin_name = str(scenario_input.get("plugin", "example_plugin"))
        plugin_dir = str(scenario_input.get("plugin_dir", "plugins"))
        tool_input = str(scenario_input.get("input", "arena"))

        src = Path(plugin_dir) / f"{plugin_name}.py"
        if not src.exists():
            return DriverResult(success=False, error=f"fixture plugin not found: {src}")
        sha = hashlib.sha256(src.read_bytes()).hexdigest()

        config_path = context.workdir / "plugin_config.json"
        config_path.write_text(
            json.dumps({"plugins": {plugin_name: {"enabled": True, "sha256": sha}}}),
            encoding="utf-8",
        )

        manager = PluginManager(plugin_dir=plugin_dir, config_path=str(config_path))
        telemetry.emit("plugin.discover")
        discovered = manager.discover_plugins()

        telemetry.emit("plugin.load", **{"arena.plugin": plugin_name})
        plugin = manager.load_plugin(plugin_name)
        loaded = plugin is not None

        invoked: str | None = None
        if plugin is not None:
            tools = plugin.get_tools()
            if tools:
                with telemetry.span("plugin.invoke", **{"arena.plugin": plugin_name}):
                    invoked = str(tools[0](tool_input))
            manager.unload_plugin(plugin_name)
            telemetry.emit("plugin.unload", **{"arena.plugin": plugin_name})

        loaded_now = manager.get_loaded_plugins()
        still_loaded = plugin_name in loaded_now if isinstance(loaded_now, (dict, list, set, tuple)) else True
        unloaded = not still_loaded

        success = loaded and invoked is not None and unloaded
        return DriverResult(
            success=success,
            raw_output=invoked or "",
            structured_output={
                "discovered": list(discovered),
                "loaded": loaded,
                "invoked": invoked,
                "unloaded": unloaded,
            },
            extra_metrics={"plugin_ok": 1.0 if success else 0.0},
        )
