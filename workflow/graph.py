"""LangGraph Workflow Implementation - HENK Agent System.

This module implements the LangGraph StateGraph with:
- 4 Agent Nodes: Operator, HENK1, Design HENK, LASERHENK
- Tool Nodes: RAG, CRM, DALLE, SAIA
- Conditional Edges based on Operator logic
- HITL (Human-in-the-Loop) Interrupts
"""

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from agents.design_henk import DesignHenkAgent
from agents.henk1 import Henk1Agent
from agents.laserhenk import LaserHenkAgent
from agents.operator import OperatorAgent
from models.graph_state import HenkGraphState
from tools.crm_tool import CRMTool
from tools.dalle_tool import DALLETool
from tools.rag_tool import RAGTool
from tools.saia_tool import SAIATool


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _add_message(state: HenkGraphState, role: str, content: str, agent: str, **kwargs) -> None:
    """Add message to conversation history."""
    message = {"role": role, "content": content, "agent": agent}
    message.update(kwargs)
    state["messages"].append(message)


def _create_agent_node(agent_class, agent_name: str):
    """Factory function to create agent nodes with consistent logic."""
    async def agent_node(state: HenkGraphState) -> HenkGraphState:
        agent = agent_class()
        decision = await agent.process(state["session_state"])

        # Update state
        if agent_name != "operator":
            state["current_agent"] = agent_name
        state["next_agent"] = decision.next_agent
        state["pending_action"] = decision.action
        state["action_params"] = decision.action_params

        # Add agent message
        if decision.message:
            _add_message(state, "assistant", f"[{agent_name.upper()}] {decision.message}", agent_name)

        return state

    agent_node.__name__ = f"{agent_name}_node"
    agent_node.__doc__ = f"{agent_name.upper()} Agent Node"
    return agent_node


# Create agent nodes using factory
operator_node = _create_agent_node(OperatorAgent, "operator")
henk1_node = _create_agent_node(Henk1Agent, "henk1")
design_henk_node = _create_agent_node(DesignHenkAgent, "design_henk")
laserhenk_node = _create_agent_node(LaserHenkAgent, "laserhenk")


# ============================================================================
# TOOL NODES
# ============================================================================


async def rag_tool_node(state: HenkGraphState) -> HenkGraphState:
    """RAG Tool Node - PostgreSQL Database Queries."""
    rag_tool = RAGTool()
    query_text = state.get("action_params", {}).get("query", "")

    from models.tools import RAGQuery
    query = RAGQuery(query=query_text, top_k=5)
    result = await rag_tool.query(query)

    # Store result
    state["rag_output"] = {"results": result.results, "metadata": result.metadata}
    state["session_state"].rag_context = result.results

    _add_message(state, "system", f"[RAG] Retrieved {len(result.results)} results", "rag_tool")

    # Clear pending action
    state["pending_action"] = None
    state["action_params"] = None

    return state


async def crm_tool_node(state: HenkGraphState) -> HenkGraphState:
    """CRM Tool Node - PIPEDRIVE Lead Management with HITL interrupt."""
    crm_tool = CRMTool()
    action = state.get("pending_action")
    params = state.get("action_params", {})

    if action == "create_crm_lead":
        from models.tools import CRMLeadCreate

        lead_data = CRMLeadCreate(
            customer_name=state["session_state"].customer.name or "Unknown",
            email=state["session_state"].customer.email,
            phone=state["session_state"].customer.phone,
            notes=f"Session: {state['session_state'].session_id}"
        )

        result = await crm_tool.create_lead(lead_data)

        # Store result
        state["crm_output"] = {
            "lead_id": result.lead_id,
            "success": result.success,
            "message": result.message
        }
        state["session_state"].customer.crm_lead_id = result.lead_id

        _add_message(state, "system", f"[CRM] Lead created: {result.lead_id}", "crm_tool")
        _add_message(
            state, "system",
            "[HITL] Human review required for CRM lead",
            "hitl_interrupt",
            interrupt_type="crm_lead_approval"
        )

    state["pending_action"] = None
    state["action_params"] = None
    return state


async def dalle_tool_node(state: HenkGraphState) -> HenkGraphState:
    """DALLE Tool Node - AI Image Generation."""
    dalle_tool = DALLETool()
    params = state.get("action_params", {})
    design_prefs = params.get("design_preferences", {})
    customer_context = params.get("customer_context")

    prompt = dalle_tool.build_prompt_from_context(design_prefs, customer_context)

    from models.tools import DALLEImageRequest
    request = DALLEImageRequest(prompt=prompt, size="1024x1024", quality="standard")
    result = await dalle_tool.generate_image(request)

    # Store result
    state["dalle_output"] = {
        "image_url": result.image_url,
        "revised_prompt": result.revised_prompt,
        "success": result.success
    }
    state["session_state"].mood_image_url = result.image_url

    _add_message(state, "system", f"[DALLE] Image generated: {result.image_url}", "dalle_tool")

    state["pending_action"] = None
    state["action_params"] = None
    return state


async def saia_tool_node(state: HenkGraphState) -> HenkGraphState:
    """SAIA Tool Node - 3D Body Measurement."""
    saia_tool = SAIATool()
    params = state.get("action_params", {})

    from models.tools import SAIAMeasurementRequest
    request = SAIAMeasurementRequest(
        customer_id=params.get("customer_id", ""),
        scan_type=params.get("scan_type", "full_body")
    )

    result = await saia_tool.request_measurement(request)

    # Store result
    state["saia_output"] = {
        "measurement_id": result.measurement_id,
        "success": result.success,
        "measurements": result.measurements or {}
    }

    # Update session state if measurements available
    if result.measurements:
        from models.customer import Measurements
        state["session_state"].measurements = Measurements(**result.measurements)

    _add_message(state, "system", f"[SAIA] Measurement completed: {result.measurement_id}", "saia_tool")

    state["pending_action"] = None
    state["action_params"] = None
    return state


# ============================================================================
# CONDITIONAL EDGE FUNCTIONS
# ============================================================================


def route_from_operator(state: HenkGraphState) -> Literal["henk1", "design_henk", "laserhenk", "end"]:
    """Route from Operator to appropriate agent."""
    next_agent = state.get("next_agent")

    if next_agent == "henk1":
        return "henk1"
    elif next_agent == "design_henk":
        return "design_henk"
    elif next_agent == "laserhenk":
        return "laserhenk"
    else:
        return "end"


def route_from_agent(
    state: HenkGraphState
) -> Literal["operator", "rag_tool", "crm_tool", "dalle_tool", "saia_tool"]:
    """Route from agent to tool or back to operator."""
    pending_action = state.get("pending_action")

    # Route to appropriate tool
    action_to_tool = {
        "query_rag": "rag_tool",
        "create_crm_lead": "crm_tool",
        "generate_dalle_image": "dalle_tool",
        "request_saia_measurement": "saia_tool",
    }

    return action_to_tool.get(pending_action, "operator")


def route_laserhenk_measurement(
    state: HenkGraphState
) -> Literal["saia_tool", "hitl_interrupt", "operator"]:
    """Route LASERHENK measurement method (SAIA OR HITL)."""
    pending_action = state.get("pending_action")

    if pending_action == "request_saia_measurement":
        return "saia_tool"
    elif pending_action == "schedule_manual_measurement":
        return "hitl_interrupt"
    else:
        return "operator"


def route_from_tools(
    state: HenkGraphState
) -> Literal["henk1", "design_henk", "laserhenk", "operator"]:
    """Route from tools back to requesting agent."""
    current_agent = state.get("current_agent", "operator")

    if current_agent in ["henk1", "design_henk", "laserhenk"]:
        return current_agent
    return "operator"


# ============================================================================
# HITL INTERRUPT NODE
# ============================================================================


async def hitl_interrupt_node(state: HenkGraphState) -> HenkGraphState:
    """HITL (Human-in-the-Loop) Interrupt Node - Pauses workflow for human intervention."""
    _add_message(state, "system", "[HITL] Workflow paused. Awaiting human intervention.", "hitl_interrupt")
    return state


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================


def create_henk_graph() -> StateGraph:
    """
    Create the HENK LangGraph StateGraph.

    Returns:
        Compiled StateGraph ready for execution
    """
    graph = StateGraph(HenkGraphState)

    # Add agent nodes
    graph.add_node("operator", operator_node)
    graph.add_node("henk1", henk1_node)
    graph.add_node("design_henk", design_henk_node)
    graph.add_node("laserhenk", laserhenk_node)

    # Add tool nodes
    graph.add_node("rag_tool", rag_tool_node)
    graph.add_node("crm_tool", crm_tool_node)
    graph.add_node("dalle_tool", dalle_tool_node)
    graph.add_node("saia_tool", saia_tool_node)

    # Add HITL interrupt node
    graph.add_node("hitl_interrupt", hitl_interrupt_node)

    # Entry point
    graph.add_edge(START, "operator")

    # Operator routing
    graph.add_conditional_edges(
        "operator",
        route_from_operator,
        {"henk1": "henk1", "design_henk": "design_henk", "laserhenk": "laserhenk", "end": END}
    )

    # Agent routing
    for agent in ["henk1", "design_henk"]:
        graph.add_conditional_edges(
            agent,
            route_from_agent,
            {
                "operator": "operator",
                "rag_tool": "rag_tool",
                "crm_tool": "crm_tool",
                "dalle_tool": "dalle_tool",
                "saia_tool": "saia_tool"
            }
        )

    # LASERHENK special routing (SAIA OR HITL)
    graph.add_conditional_edges(
        "laserhenk",
        route_laserhenk_measurement,
        {"saia_tool": "saia_tool", "hitl_interrupt": "hitl_interrupt", "operator": "operator"}
    )

    # Tool routing back to agents
    for tool_node in ["rag_tool", "dalle_tool", "saia_tool"]:
        graph.add_conditional_edges(
            tool_node,
            route_from_tools,
            {"operator": "operator", "henk1": "henk1", "design_henk": "design_henk", "laserhenk": "laserhenk"}
        )

    # CRM Tool → HITL Interrupt → Design HENK
    graph.add_edge("crm_tool", "hitl_interrupt")
    graph.add_edge("hitl_interrupt", "design_henk")

    # Compile with checkpointing
    memory = MemorySaver()
    compiled_graph = graph.compile(
        checkpointer=memory,
        interrupt_before=["hitl_interrupt"]
    )

    return compiled_graph


# ============================================================================
# WORKFLOW EXECUTION
# ============================================================================


async def run_henk_workflow(
    initial_state: HenkGraphState,
    thread_id: str = "default"
) -> dict:
    """
    Run the HENK workflow.

    Args:
        initial_state: Initial graph state
        thread_id: Thread ID for checkpointing (enables pause/resume)

    Returns:
        Final state after workflow execution
    """
    graph = create_henk_graph()

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 50
    }

    final_state = await graph.ainvoke(initial_state, config)
    return final_state


async def resume_henk_workflow(
    thread_id: str,
    user_input: dict | None = None
) -> dict:
    """
    Resume a paused HENK workflow after HITL intervention.

    Args:
        thread_id: Thread ID of paused workflow
        user_input: Optional user input to inject after interrupt

    Returns:
        Final state after workflow resumption
    """
    graph = create_henk_graph()

    config = {"configurable": {"thread_id": thread_id}}

    # Get current state
    state = await graph.aget_state(config)

    # Inject user input if provided
    if user_input:
        state.values["messages"].append(user_input)

    # Resume execution
    final_state = await graph.ainvoke(None, config)
    return final_state
