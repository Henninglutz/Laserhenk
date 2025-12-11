"""CRM Blueprint - Pipedrive Integration."""

import os
from typing import List, Optional
from datetime import datetime

import requests
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from pydantic import BaseModel, Field

from app.middleware import get_current_user_id, beta_user_required

crm_bp = Blueprint('crm', __name__)

# Pipedrive API Configuration
PIPEDRIVE_API_KEY = os.getenv('PIPEDRIVE_API_KEY')
PIPEDRIVE_DOMAIN = os.getenv('PIPEDRIVE_DOMAIN', 'api.pipedrive.com')


class PipedriveClient:
    """Pipedrive API Client."""

    def __init__(self, api_key: str, domain: str = 'api.pipedrive.com'):
        """
        Initialize Pipedrive Client.

        Args:
            api_key: Pipedrive API Key
            domain: Pipedrive API domain
        """
        self.api_key = api_key
        self.domain = domain
        self.base_url = f'https://{domain}/v1'

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Make API request to Pipedrive.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            API response data

        Raises:
            requests.HTTPError: On API error
        """
        url = f'{self.base_url}/{endpoint}'
        params = kwargs.get('params', {})
        params['api_token'] = self.api_key

        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=kwargs.get('json'),
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    def create_person(self, name: str, email: str, phone: Optional[str] = None) -> dict:
        """
        Erstelle Person in Pipedrive.

        Args:
            name: Name
            email: Email
            phone: Telefon (optional)

        Returns:
            Person data
        """
        data = {
            'name': name,
            'email': [email],
        }
        if phone:
            data['phone'] = [phone]

        result = self._request('POST', 'persons', json=data)
        return result.get('data', {})

    def create_deal(
        self,
        title: str,
        person_id: int,
        value: float,
        currency: str = 'EUR',
        stage_id: Optional[int] = None,
    ) -> dict:
        """
        Erstelle Deal in Pipedrive.

        Args:
            title: Deal title
            person_id: Person ID
            value: Deal value
            currency: Currency code
            stage_id: Pipeline stage ID

        Returns:
            Deal data
        """
        data = {
            'title': title,
            'person_id': person_id,
            'value': value,
            'currency': currency,
        }
        if stage_id:
            data['stage_id'] = stage_id

        result = self._request('POST', 'deals', json=data)
        return result.get('data', {})

    def get_deals(self, person_id: Optional[int] = None) -> List[dict]:
        """
        Hole Deals.

        Args:
            person_id: Optional Person ID filter

        Returns:
            List of deals
        """
        params = {}
        if person_id:
            params['person_id'] = person_id

        result = self._request('GET', 'deals', params=params)
        return result.get('data', [])

    def get_person_by_email(self, email: str) -> Optional[dict]:
        """
        Finde Person by Email.

        Args:
            email: Email address

        Returns:
            Person data oder None
        """
        result = self._request('GET', 'persons/search', params={'term': email, 'fields': 'email'})
        items = result.get('data', {}).get('items', [])

        for item in items:
            person = item.get('item', {})
            # Check if email matches exactly
            person_emails = person.get('emails', [])
            if any(e.get('value', '').lower() == email.lower() for e in person_emails):
                return person

        return None

    def update_deal(self, deal_id: int, **kwargs) -> dict:
        """
        Update Deal.

        Args:
            deal_id: Deal ID
            **kwargs: Fields to update

        Returns:
            Updated deal data
        """
        result = self._request('PUT', f'deals/{deal_id}', json=kwargs)
        return result.get('data', {})


def get_pipedrive_client() -> Optional[PipedriveClient]:
    """
    Erstelle Pipedrive Client.

    Returns:
        PipedriveClient oder None wenn nicht konfiguriert
    """
    if not PIPEDRIVE_API_KEY:
        return None

    return PipedriveClient(api_key=PIPEDRIVE_API_KEY, domain=PIPEDRIVE_DOMAIN)


@crm_bp.route('/lead', methods=['POST'])
@jwt_required()
def create_lead():
    """
    Erstelle Lead in Pipedrive.

    Body:
        - name: str
        - email: str
        - phone: str (optional)
        - deal_title: str (optional)
        - deal_value: float (optional)

    Returns:
        201: Lead erstellt
        400: Validation error
        503: Pipedrive nicht konfiguriert
    """
    client = get_pipedrive_client()
    if not client:
        return jsonify({'error': 'Pipedrive nicht konfiguriert'}), 503

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')

    if not name or not email:
        return jsonify({'error': 'Name und Email sind erforderlich'}), 400

    try:
        # Check if person exists
        person = client.get_person_by_email(email)

        if not person:
            # Create new person
            person = client.create_person(name=name, email=email, phone=phone)

        person_id = person['id']

        # Create deal if requested
        deal = None
        if data.get('deal_title'):
            deal = client.create_deal(
                title=data['deal_title'],
                person_id=person_id,
                value=data.get('deal_value', 0),
                currency='EUR',
            )

        return jsonify({
            'message': 'Lead erfolgreich erstellt',
            'person_id': person_id,
            'deal_id': deal['id'] if deal else None,
        }), 201

    except requests.HTTPError as e:
        return jsonify({'error': 'Pipedrive API error', 'message': str(e)}), 500


@crm_bp.route('/deals', methods=['GET'])
@beta_user_required
def get_user_deals():
    """
    Hole Deal-Historie für aktuellen User (Beta-Feature).

    Diese Route ist nur für Beta-User verfügbar.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        - email: str (optional) - Filter by customer email

    Returns:
        200: Liste von Deals
        403: Nicht Beta-User
        503: Pipedrive nicht konfiguriert
    """
    client = get_pipedrive_client()
    if not client:
        return jsonify({'error': 'Pipedrive nicht konfiguriert'}), 503

    # Optional: Filter by email
    email = request.args.get('email')
    person_id = None

    if email:
        person = client.get_person_by_email(email)
        if person:
            person_id = person['id']

    try:
        deals = client.get_deals(person_id=person_id)

        # Format deals
        formatted_deals = []
        for deal in deals:
            formatted_deals.append({
                'id': deal['id'],
                'title': deal['title'],
                'value': deal['value'],
                'currency': deal['currency'],
                'status': deal['status'],
                'stage_id': deal['stage_id'],
                'person_name': deal.get('person_name'),
                'created_at': deal.get('add_time'),
                'updated_at': deal.get('update_time'),
            })

        return jsonify({
            'deals': formatted_deals,
            'count': len(formatted_deals),
        }), 200

    except requests.HTTPError as e:
        return jsonify({'error': 'Pipedrive API error', 'message': str(e)}), 500


@crm_bp.route('/deal/<int:deal_id>', methods=['GET'])
@beta_user_required
def get_deal_details(deal_id: int):
    """
    Hole Details für einen Deal (Beta-Feature).

    Args:
        deal_id: Deal ID

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        200: Deal details
        404: Deal not found
        503: Pipedrive nicht konfiguriert
    """
    client = get_pipedrive_client()
    if not client:
        return jsonify({'error': 'Pipedrive nicht konfiguriert'}), 503

    try:
        result = client._request('GET', f'deals/{deal_id}')
        deal = result.get('data', {})

        if not deal:
            return jsonify({'error': 'Deal nicht gefunden'}), 404

        return jsonify({
            'deal': {
                'id': deal['id'],
                'title': deal['title'],
                'value': deal['value'],
                'currency': deal['currency'],
                'status': deal['status'],
                'stage_id': deal['stage_id'],
                'person_name': deal.get('person_name'),
                'created_at': deal.get('add_time'),
                'updated_at': deal.get('update_time'),
                'won_time': deal.get('won_time'),
                'lost_time': deal.get('lost_time'),
            }
        }), 200

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify({'error': 'Deal nicht gefunden'}), 404
        return jsonify({'error': 'Pipedrive API error', 'message': str(e)}), 500


@crm_bp.route('/deal/<int:deal_id>', methods=['PUT'])
@jwt_required()
def update_deal(deal_id: int):
    """
    Update Deal in Pipedrive.

    Args:
        deal_id: Deal ID

    Body:
        - stage_id: int (optional)
        - value: float (optional)
        - status: str (optional)
        - title: str (optional)

    Returns:
        200: Deal updated
        404: Deal not found
        503: Pipedrive nicht konfiguriert
    """
    client = get_pipedrive_client()
    if not client:
        return jsonify({'error': 'Pipedrive nicht konfiguriert'}), 503

    data = request.get_json()

    try:
        deal = client.update_deal(deal_id, **data)

        return jsonify({
            'message': 'Deal erfolgreich aktualisiert',
            'deal': deal,
        }), 200

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify({'error': 'Deal nicht gefunden'}), 404
        return jsonify({'error': 'Pipedrive API error', 'message': str(e)}), 500
