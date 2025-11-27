"""Flask Web Application for HENK Agent System."""

import asyncio
import os
import uuid

from flask import Flask, render_template, request, jsonify, session

from models.graph_state import create_initial_graph_state
from workflow.graph import run_henk_workflow, resume_henk_workflow

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# ============================================================================
# ROUTES
# ============================================================================


@app.route('/')
def index():
    """Redirect to LASERHENK."""
    from flask import redirect, url_for
    return redirect(url_for('laserhenk_home'))


@app.route('/LASERHENK')
def laserhenk_home():
    """LASERHENK main interface."""
    return render_template('laserhenk.html')


@app.route('/LASERHENK/session/new', methods=['POST'])
def create_session():
    """Create new customer session."""
    data = request.get_json() or {}
    customer_id = data.get('customer_id')

    # Create session
    session_id = str(uuid.uuid4())
    initial_state = create_initial_graph_state(session_id)

    if customer_id:
        initial_state['session_state'].customer.customer_id = customer_id

    # Store session in Flask session (or database)
    session['henk_session_id'] = session_id

    return jsonify({
        'success': True,
        'session_id': session_id,
        'message': 'Session created successfully'
    })


@app.route('/LASERHENK/workflow/start', methods=['POST'])
def start_workflow():
    """Start HENK workflow."""
    session_id = session.get('henk_session_id')

    if not session_id:
        return jsonify({'error': 'No active session'}), 400

    # Start workflow
    initial_state = create_initial_graph_state(session_id)

    try:
        final_state = asyncio.run(run_henk_workflow(
            initial_state=initial_state,
            thread_id=session_id
        ))

        return jsonify({
            'success': True,
            'current_agent': final_state.get('current_agent'),
            'next_agent': final_state.get('next_agent'),
            'messages': final_state.get('messages', [])
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/LASERHENK/workflow/resume', methods=['POST'])
def resume_workflow():
    """Resume workflow after HITL interrupt."""
    session_id = session.get('henk_session_id')
    data = request.get_json()

    if not session_id:
        return jsonify({'error': 'No active session'}), 400

    user_input = data.get('user_input')

    try:
        final_state = asyncio.run(resume_henk_workflow(
            thread_id=session_id,
            user_input=user_input
        ))

        return jsonify({
            'success': True,
            'current_agent': final_state.get('current_agent'),
            'messages': final_state.get('messages', [])
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/LASERHENK/agents')
def get_agents():
    """Get available agents info."""
    agents = [
        {
            'name': 'Operator',
            'description': 'Routes to specialized agents',
            'phase': 'Routing'
        },
        {
            'name': 'HENK1',
            'description': 'Needs assessment (AIDA)',
            'phase': 'Phase 1'
        },
        {
            'name': 'Design HENK',
            'description': 'Design preferences & CRM lead',
            'phase': 'Phase 2'
        },
        {
            'name': 'LASERHENK',
            'description': 'Measurements (SAIA/HITL)',
            'phase': 'Phase 3'
        }
    ]

    return jsonify({'agents': agents})


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.errorhandler(404)
def not_found(error):
    """404 handler."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """500 handler."""
    return render_template('500.html'), 500


# ============================================================================
# MAIN
# ============================================================================


if __name__ == '__main__':
    # Development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
