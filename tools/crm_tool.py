"""CRM Tool - Pipedrive API Integration (NEW)."""

import os
from typing import Optional

import requests
from models.tools import CRMLeadCreate, CRMLeadResponse, CRMLeadUpdate


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
        Make API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Request parameters

        Returns:
            Response data
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
        """Create person."""
        data = {'name': name, 'email': [email]}
        if phone:
            data['phone'] = [phone]
        result = self._request('POST', 'persons', json=data)
        return result.get('data', {})

    def get_person_by_email(self, email: str) -> Optional[dict]:
        """Find person by email."""
        result = self._request('GET', 'persons/search', params={'term': email, 'fields': 'email'})
        items = result.get('data', {}).get('items', [])
        for item in items:
            person = item.get('item', {})
            emails = person.get('emails', [])
            if any(e.get('value', '').lower() == email.lower() for e in emails):
                return person
        return None

    def create_deal(self, title: str, person_id: int, value: float, currency: str = 'EUR') -> dict:
        """Create deal."""
        data = {'title': title, 'person_id': person_id, 'value': value, 'currency': currency}
        result = self._request('POST', 'deals', json=data)
        return result.get('data', {})


class CRMTool:
    """
    CRM Tool mit echter Pipedrive-Integration.

    Ersetzt die alte Placeholder-Implementierung.
    """

    def __init__(self, api_key: Optional[str] = None, domain: Optional[str] = None):
        """
        Initialize CRM Tool.

        Args:
            api_key: Pipedrive API key (defaults to env var)
            domain: Pipedrive domain (defaults to env var)
        """
        self.api_key = api_key or os.getenv('PIPEDRIVE_API_KEY')
        self.domain = domain or os.getenv('PIPEDRIVE_DOMAIN', 'api.pipedrive.com')

        if self.api_key:
            self.client = PipedriveClient(self.api_key, self.domain)
        else:
            self.client = None

    async def create_lead(self, lead_data: CRMLeadCreate) -> CRMLeadResponse:
        """
        Create lead in Pipedrive.

        Args:
            lead_data: Lead creation data

        Returns:
            CRM response
        """
        if not self.client:
            return CRMLeadResponse(
                lead_id='no_api_key',
                success=False,
                message='Pipedrive API key not configured',
            )

        # Validate email (required for Pipedrive person creation)
        if not lead_data.email:
            return CRMLeadResponse(
                lead_id='no_email',
                success=False,
                message='Email ist erforderlich für CRM Lead-Erstellung',
            )

        try:
            # Check if person exists
            person = self.client.get_person_by_email(lead_data.email)

            if not person:
                # Create new person
                person = self.client.create_person(
                    name=lead_data.customer_name,
                    email=lead_data.email,
                    phone=lead_data.phone,
                )

            person_id = person['id']

            # Create deal if value provided
            deal_id = None
            if lead_data.deal_value and lead_data.deal_value > 0:
                deal = self.client.create_deal(
                    title=f"Lead: {lead_data.customer_name}",
                    person_id=person_id,
                    value=lead_data.deal_value,
                    currency='EUR',
                )
                deal_id = str(deal['id'])

            return CRMLeadResponse(
                lead_id=str(person_id),
                deal_id=deal_id,
                success=True,
                message=f'Lead erfolgreich erstellt (Person ID: {person_id})',
            )

        except Exception as e:
            return CRMLeadResponse(
                lead_id='error',
                success=False,
                message=f'Fehler beim Erstellen des Leads: {str(e)}',
            )

    async def update_lead(self, update_data: CRMLeadUpdate) -> CRMLeadResponse:
        """
        Update lead in Pipedrive.

        Args:
            update_data: Update data

        Returns:
            CRM response
        """
        if not self.client:
            return CRMLeadResponse(
                lead_id=update_data.lead_id,
                success=False,
                message='Pipedrive API key not configured',
            )

        try:
            # Update person
            self.client._request(
                'PUT',
                f'persons/{update_data.lead_id}',
                json=update_data.updates,
            )

            return CRMLeadResponse(
                lead_id=update_data.lead_id,
                success=True,
                message='Lead erfolgreich aktualisiert',
            )

        except Exception as e:
            return CRMLeadResponse(
                lead_id=update_data.lead_id,
                success=False,
                message=f'Fehler beim Aktualisieren: {str(e)}',
            )
