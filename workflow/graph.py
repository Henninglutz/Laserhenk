"""LangGraph Workflow Implementation - HENK Agent System.

This module implements the LangGraph StateGraph with:
- 4 Agent Nodes: Operator, HENK1, Design HENK, LASERHENK
- Tool Nodes: RAG, CRM, DALLE, SAIA
- Conditional Edges based on Operator logic
- HITL (Human-in-the-Loop) Interrupts
"""

from typing import Literal

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
# AGENT NODES
# ============================================================================


async def operator_node(state: HenkGraphState) -> HenkGraphState:
    """
    Operator Agent Node.

    Routes to specialized agents based on session state.
    """
    operator = OperatorAgent()
    decision = await operator.process(state["session_state"])

    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    # Add operator message to conversation
    if decision.message:
        state["messages"].append({
            "role": "assistant",
            "content": f"[Operator] {decision.message}",
            "agent": "operator"
        })

    return state


async def henk1_node(state: HenkGraphState) -> HenkGraphState:
    """
    HENK1 Agent Node - Bedarfsermittlung.

    Handles needs assessment using AIDA principle.
    """
    henk1 = Henk1Agent()
    decision = await henk1.process(state["session_state"])

    state["current_agent"] = "henk1"
    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    # Add HENK1 message
    if decision.message:
        state["messages"].append({
            "role": "assistant",
            "content": f"[HENK1] {decision.message}",
            "agent": "henk1"
        })

    # DEMO: Simulate customer ID creation to progress workflow
    if not state["session_state"].customer.customer_id:
        state["session_state"].customer.customer_id = f"CUST_{state['session_state'].session_id[:8]}"
        state["messages"].append({
            "role": "system",
            "content": f"[HENK1] Customer registered: {state['session_state'].customer.customer_id}",
            "agent": "henk1"
        })

    return state


async def design_henk_node(state: HenkGraphState) -> HenkGraphState:
    """
    Design HENK Agent Node - Design Präferenzen & Leadsicherung.

    Handles:
    - Design preference collection
    - RAG queries for design options
    - DALLE mood image generation
    - CRM lead creation (triggers HITL interrupt)
    """
    design_henk = DesignHenkAgent()
    decision = await design_henk.process(state["session_state"])

    state["current_agent"] = "design_henk"
    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    # Add Design HENK message
    if decision.message:
        state["messages"].append({
            "role": "assistant",
            "content": f"[Design HENK] {decision.message}",
            "agent": "design_henk"
        })

    # DEMO: Simulate design preferences to progress workflow
    if not state["session_state"].design_preferences.revers_type and decision.action == "collect_preferences":
        state["session_state"].design_preferences.revers_type = "spitz"
        state["session_state"].design_preferences.shoulder_padding = True
        state["messages"].append({
            "role": "system",
            "content": "[Design HENK] Design preferences collected (demo)",
            "agent": "design_henk"
        })

    return state


async def laserhenk_node(state: HenkGraphState) -> HenkGraphState:
    """
    LASERHENK Agent Node - Maßerfassung.

    Handles measurement collection via:
    - SAIA 3D Tool (automatic measurement) OR
    - HITL (manual appointment scheduling)
    """
    laserhenk = LaserHenkAgent()
    decision = await laserhenk.process(state["session_state"])

    state["current_agent"] = "laserhenk"
    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    # Add LASERHENK message
    if decision.message:
        state["messages"].append({
            "role": "assistant",
            "content": f"[LASERHENK] {decision.message}",
            "agent": "laserhenk"
        })

    # DEMO: Simulate measurements after SAIA tool call
    if state.get("saia_output") and not state["session_state"].measurements:
        from models.customer import Measurements
        state["session_state"].measurements = Measurements(
            chest_cm=100.0,
            waist_cm=85.0,
            hips_cm=95.0
        )
        state["messages"].append({
            "role": "system",
            "content": "[LASERHENK] Measurements received (demo)",
            "agent": "laserhenk"
        })

    return state


# ============================================================================
# TOOL NODES
# ============================================================================


async def rag_tool_node(state: HenkGraphState) -> HenkGraphState:
    """
    RAG Tool Node - PostgreSQL Database Queries.

    Executes RAG queries for:
    - Product catalog information
    - Design options
    - Customer history
    - Fabric recommendations
    """
    rag_tool = RAGTool()

    # Get query from pending action params
    query_text = state.get("action_params", {}).get("query", "")

    from models.tools import RAGQuery
    query = RAGQuery(query=query_text, top_k=5)

    # Execute RAG query
    result = await rag_tool.query(query)

    # Store result in state
    state["rag_output"] = {
        "results": result.results,
        "metadata": result.metadata
    }

    # Update session state with RAG context
    state["session_state"].rag_context = result.results

    # Add tool output message
    state["messages"].append({
        "role": "system",
        "content": f"[RAG Tool] Retrieved {len(result.results)} results for query: {query_text}",
        "agent": "rag_tool"
    })

    # Clear pending action and route back to current agent
    state["pending_action"] = None
    state["action_params"] = None

    return state


async def crm_tool_node(state: HenkGraphState) -> HenkGraphState:
    """
    CRM Tool Node - PIPEDRIVE Lead Management.

    Creates and updates leads in PIPEDRIVE CRM.
    This node triggers a HITL interrupt after lead creation.
    """
    crm_tool = CRMTool()

    action = state.get("pending_action")
    params = state.get("action_params", {})

    if action == "create_crm_lead":
        from models.tools import CRMLeadCreate

        # Build lead data from state
        lead_data = CRMLeadCreate(
            customer_name=state["session_state"].customer.name or "Unknown",
            customer_email=state["session_state"].customer.email,
            customer_phone=state["session_state"].customer.phone_number,
            design_preferences=params.get("design_preferences"),
            mood_image_url=params.get("mood_image"),
            notes=f"Session: {state['session_state'].session_id}"
        )

        # Create lead
        result = await crm_tool.create_lead(lead_data)

        # Store result
        state["crm_output"] = {
            "lead_id": result.lead_id,
            "success": result.success,
            "message": result.message
        }

        # Update customer with CRM lead ID
        state["session_state"].customer.crm_lead_id = result.lead_id

        # Add success message
        state["messages"].append({
            "role": "system",
            "content": f"[CRM Tool] Lead created successfully: {result.lead_id}",
            "agent": "crm_tool"
        })

        # HITL INTERRUPT: After CRM lead creation, human review is required
        # This will pause the workflow here until human approval
        state["messages"].append({
            "role": "system",
            "content": "[HITL] Human review required for CRM lead. Please approve to continue.",
            "agent": "hitl_interrupt",
            "interrupt_type": "crm_lead_approval"
        })

    # Clear pending action
    state["pending_action"] = None
    state["action_params"] = None

    return state


async def dalle_tool_node(state: HenkGraphState) -> HenkGraphState:
    """
    DALLE Tool Node - AI Image Generation.

    Generates mood boards and design visualizations using DALLE.
    """
    dalle_tool = DALLETool()

    params = state.get("action_params", {})
    design_prefs = params.get("design_preferences", {})
    customer_context = params.get("customer_context")

    # Build prompt from preferences and context
    prompt = dalle_tool.build_prompt_from_context(
        design_preferences=design_prefs,
        customer_context=customer_context
    )

    from models.tools import DALLEImageRequest
    request = DALLEImageRequest(
        prompt=prompt,
        size="1024x1024",
        quality="standard"
    )

    # Generate image
    result = await dalle_tool.generate_image(request)

    # Store result
    state["dalle_output"] = {
        "image_url": result.image_url,
        "revised_prompt": result.revised_prompt,
        "success": result.success
    }

    # Update session state with mood image
    state["session_state"].mood_image_url = result.image_url

    # Add success message
    state["messages"].append({
        "role": "system",
        "content": f"[DALLE Tool] Mood image generated: {result.image_url}",
        "agent": "dalle_tool"
    })

    # Clear pending action
    state["pending_action"] = None
    state["action_params"] = None

    return state


async def saia_tool_node(state: HenkGraphState) -> HenkGraphState:
    """
    SAIA Tool Node - 3D Body Measurement.

    Executes 3D body scanning via SAIA API.
    Alternative to HITL manual measurement.
    """
    saia_tool = SAIATool()

    params = state.get("action_params", {})

    from models.tools import SAIAMeasurementRequest
    request = SAIAMeasurementRequest(
        customer_id=params.get("customer_id", ""),
        scan_type=params.get("scan_type", "full_body")
    )

    # Request measurement
    result = await saia_tool.request_measurement(request)

    # Store result
    state["saia_output"] = {
        "measurement_id": result.measurement_id,
        "success": result.success,
        "measurements": result.measurements or {}
    }

    # If measurements available, update session state
    if result.measurements:
        from models.customer import Measurements
        state["session_state"].measurements = Measurements(
            **result.measurements
        )

    # Add success message
    state["messages"].append({
        "role": "system",
        "content": f"[SAIA Tool] 3D measurement completed: {result.measurement_id}",
        "agent": "saia_tool"
    })

    # Clear pending action
    state["pending_action"] = None
    state["action_params"] = None

    return state


# ============================================================================
# CONDITIONAL EDGE FUNCTIONS
# ============================================================================


def route_from_operator(
    state: HenkGraphState
) -> Literal["henk1", "design_henk", "laserhenk", "end"]:
    """
    Conditional edge from Operator node.

    Routes to appropriate agent based on operator decision.
    """
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
    """
    Conditional edge from agent nodes (HENK1, Design HENK, LASERHENK).

    Routes to:
    - Tool nodes if action required
    - Operator for re-routing
    """
    pending_action = state.get("pending_action")

    # Route to appropriate tool based on action
    if pending_action == "query_rag":
        return "rag_tool"
    elif pending_action == "create_crm_lead":
        return "crm_tool"
    elif pending_action == "generate_dalle_image":
        return "dalle_tool"
    elif pending_action == "request_saia_measurement":
        return "saia_tool"
    else:
        # No action needed, route back to operator
        return "operator"


def route_laserhenk_measurement(
    state: HenkGraphState
) -> Literal["saia_tool", "hitl_interrupt", "operator"]:
    """
    Conditional edge from LASERHENK for measurement method selection.

    Decision logic:
    - If SAIA available and customer agrees → saia_tool
    - If manual measurement needed → hitl_interrupt
    - If measurements complete → operator
    """
    pending_action = state.get("pending_action")

    if pending_action == "request_saia_measurement":
        # Route to SAIA 3D tool
        return "saia_tool"
    elif pending_action == "schedule_manual_measurement":
        # Route to HITL interrupt for appointment scheduling
        return "hitl_interrupt"
    else:
        # Measurements complete, route to operator
        return "operator"


def route_from_tools(
    state: HenkGraphState
) -> Literal["henk1", "design_henk", "laserhenk", "operator"]:
    """
    Conditional edge from tool nodes.

    Routes back to the agent that requested the tool.
    """
    current_agent = state.get("current_agent", "operator")

    if current_agent == "henk1":
        return "henk1"
    elif current_agent == "design_henk":
        return "design_henk"
    elif current_agent == "laserhenk":
        return "laserhenk"
    else:
        return "operator"


# ============================================================================
# HITL INTERRUPT NODES
# ============================================================================


async def hitl_interrupt_node(state: HenkGraphState) -> HenkGraphState:
    """
    HITL (Human-in-the-Loop) Interrupt Node.

    Pauses workflow for human intervention.
    Used for:
    - CRM Lead Approval (Design HENK)
    - Manual Measurement Appointment (LASERHENK)
    """
    # Add HITL message
    state["messages"].append({
        "role": "system",
        "content": "[HITL] Workflow paused. Awaiting human intervention.",
        "agent": "hitl_interrupt"
    })

    # Workflow will pause here until human resume
    # LangGraph's interrupt_before/interrupt_after handles this

    return state


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================


def create_henk_graph() -> StateGraph:
    """
    Create the HENK LangGraph StateGraph.

    Graph structure:
    - 4 Agent Nodes: Operator, HENK1, Design HENK, LASERHENK
    - 4 Tool Nodes: RAG, CRM, DALLE, SAIA
    - 1 HITL Interrupt Node
    - Conditional edges based on agent decisions

    Returns:
        Compiled StateGraph ready for execution
    """
    # Initialize StateGraph with HenkGraphState
    graph = StateGraph(HenkGraphState)

    # ========================================================================
    # ADD NODES
    # ========================================================================

    # Agent nodes
    graph.add_node("operator", operator_node)
    graph.add_node("henk1", henk1_node)
    graph.add_node("design_henk", design_henk_node)
    graph.add_node("laserhenk", laserhenk_node)

    # Tool nodes
    graph.add_node("rag_tool", rag_tool_node)
    graph.add_node("crm_tool", crm_tool_node)
    graph.add_node("dalle_tool", dalle_tool_node)
    graph.add_node("saia_tool", saia_tool_node)

    # HITL interrupt node
    graph.add_node("hitl_interrupt", hitl_interrupt_node)

    # ========================================================================
    # ADD EDGES
    # ========================================================================

    # Entry point: START → Operator
    graph.add_edge(START, "operator")

    # Operator → Conditional routing to agents
    graph.add_conditional_edges(
        "operator",
        route_from_operator,
        {
            "henk1": "henk1",
            "design_henk": "design_henk",
            "laserhenk": "laserhenk",
            "end": END
        }
    )

    # HENK1 → Conditional routing to tools or operator
    graph.add_conditional_edges(
        "henk1",
        route_from_agent,
        {
            "operator": "operator",
            "rag_tool": "rag_tool",
            "crm_tool": "crm_tool",
            "dalle_tool": "dalle_tool",
            "saia_tool": "saia_tool"
        }
    )

    # Design HENK → Conditional routing to tools or operator
    graph.add_conditional_edges(
        "design_henk",
        route_from_agent,
        {
            "operator": "operator",
            "rag_tool": "rag_tool",
            "crm_tool": "crm_tool",
            "dalle_tool": "dalle_tool",
            "saia_tool": "saia_tool"
        }
    )

    # LASERHENK → Special conditional routing for measurement method
    graph.add_conditional_edges(
        "laserhenk",
        route_laserhenk_measurement,
        {
            "saia_tool": "saia_tool",
            "hitl_interrupt": "hitl_interrupt",
            "operator": "operator"
        }
    )

    # Tool nodes → Route back to requesting agent
    for tool_node in ["rag_tool", "dalle_tool", "saia_tool"]:
        graph.add_conditional_edges(
            tool_node,
            route_from_tools,
            {
                "operator": "operator",
                "henk1": "henk1",
                "design_henk": "design_henk",
                "laserhenk": "laserhenk"
            }
        )

    # CRM Tool → Always route to HITL interrupt for lead approval
    graph.add_edge("crm_tool", "hitl_interrupt")

    # HITL Interrupt → Route back to Design HENK after approval
    graph.add_edge("hitl_interrupt", "design_henk")

    # ========================================================================
    # CONFIGURE INTERRUPTS
    # ========================================================================

    # Set interrupt points for HITL
    # - After CRM lead creation (handled by edge crm_tool → hitl_interrupt)
    # - Before manual measurement (LASERHENK routes to hitl_interrupt)

    # ========================================================================
    # COMPILE GRAPH
    # ========================================================================

    # Use MemorySaver for checkpointing (enables interrupts and resume)
    memory = MemorySaver()
    compiled_graph = graph.compile(
        checkpointer=memory,
        interrupt_before=["hitl_interrupt"]  # Interrupt before HITL node
    )

    return compiled_graph


# ============================================================================
# GRAPH EXECUTION HELPERS
# ============================================================================


async def run_henk_workflow(
    initial_state: HenkGraphState,
    thread_id: str = "default"
) -> dict:
    """
    Run the HENK workflow with given initial state.

    Args:
        initial_state: Initial graph state
        thread_id: Thread ID for checkpointing (enables pause/resume)

    Returns:
        Final state after workflow execution
    """
    graph = create_henk_graph()

    # Configuration for execution
    config = {
        "configurable": {
            "thread_id": thread_id
        },
        "recursion_limit": 50  # Increase recursion limit for complex workflows
    }

    # Execute graph
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

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # Get current state
    state = await graph.aget_state(config)

    # Inject user input if provided
    if user_input:
        state.values["messages"].append(user_input)

    # Resume execution
    final_state = await graph.ainvoke(None, config)

    return final_state
