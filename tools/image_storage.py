"""Image Storage Utility - Verwaltet Speicherung und Archivierung von DALL-E generierten Bildern.

SPEICHERSTRATEGIE:
------------------
1. **Lokal**: Alle Bilder in generated_images/ (automatisch beim Download)
2. **Session History**: In image_generation_history (tracking aller generierten Bilder)
3. **Approved Images**: In design_preferences.approved_image (user-bestätigte Bilder)
4. **Session Docs**: Optional in docs/<session_id>/ für langfristige Archivierung
5. **CRM**: Optional Upload zu Pipedrive als Deal-Attachment

VERWENDUNG:
-----------
```python
from tools.image_storage import ImageStorageManager

storage = ImageStorageManager()

# Bild als approved markieren
await storage.approve_image(
    session_state=state,
    image_url="https://...",
    image_type="outfit_visualization"
)

# Bild in Session Docs speichern
await storage.archive_to_session_docs(
    session_id=state.session_id,
    image_url=image_url,
    filename="approved_outfit.png"
)

# Bild zu CRM hochladen (wenn Lead vorhanden)
await storage.upload_to_crm(
    crm_lead_id=state.customer.crm_lead_id,
    image_url=image_url,
    description="Approved Outfit Design"
)
```
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx

from models.customer import SessionState

logger = logging.getLogger(__name__)


class ImageStorageManager:
    """
    Manager für Bildspeicherung und Archivierung.

    Verwaltet verschiedene Storage-Strategien für DALL-E generierte Bilder.
    """

    def __init__(self):
        """Initialize Image Storage Manager."""
        # Base directories
        self.generated_images_dir = Path(__file__).parent.parent / "generated_images"
        self.docs_dir = Path(__file__).parent.parent / "docs" / "sessions"
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        logger.info("[ImageStorage] Initialized")

    async def approve_image(
        self,
        session_state: SessionState,
        image_url: str,
        image_type: str = "outfit_visualization",
    ) -> bool:
        """
        Markiere Bild als vom User bestätigt.

        Updates:
        - design_preferences.approved_image
        - image_generation_history (approved=True)

        Args:
            session_state: Session State
            image_url: URL des zu bestätigenden Bildes
            image_type: Typ des Bildes

        Returns:
            True wenn erfolgreich
        """
        logger.info(f"[ImageStorage] Approving image: {image_url}")

        # Update approved_image in design_preferences
        session_state.design_preferences.approved_image = image_url

        # Update image_generation_history
        for img in session_state.image_generation_history:
            if img["url"] == image_url:
                img["approved"] = True
                img["approved_at"] = datetime.now().isoformat()
                break

        logger.info(f"[ImageStorage] Image approved: {image_url}")
        return True

    async def archive_to_session_docs(
        self,
        session_id: str,
        image_url: str,
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        Archiviere Bild in Session Docs Ordner.

        Erstellt: docs/sessions/<session_id>/<filename>

        Args:
            session_id: Session ID
            image_url: URL des zu archivierenden Bildes
            filename: Optional Dateiname (default: <timestamp>.png)

        Returns:
            Dateipfad oder None bei Fehler
        """
        try:
            # Create session docs directory
            session_docs_dir = self.docs_dir / session_id
            session_docs_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"approved_{timestamp}.png"

            filepath = session_docs_dir / filename

            # Check if image_url is local file or remote URL
            if image_url.startswith("http://") or image_url.startswith("https://"):
                # Download from URL
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url)
                    response.raise_for_status()
                    image_data = response.content

                with open(filepath, "wb") as f:
                    f.write(image_data)

            else:
                # Copy from local file
                local_path = Path(image_url)
                if local_path.exists():
                    shutil.copy(local_path, filepath)
                else:
                    logger.error(f"[ImageStorage] Local file not found: {image_url}")
                    return None

            logger.info(f"[ImageStorage] Archived to session docs: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"[ImageStorage] Archive failed: {e}", exc_info=True)
            return None

    async def upload_to_crm(
        self,
        crm_lead_id: str,
        image_url: str,
        description: str = "Approved Outfit Design",
    ) -> bool:
        """
        Upload Bild zu CRM (Pipedrive) als Deal Attachment.

        HINWEIS: Benötigt Pipedrive API Integration.

        Args:
            crm_lead_id: CRM Lead/Deal ID
            image_url: URL des Bildes
            description: Beschreibung für CRM

        Returns:
            True wenn erfolgreich
        """
        # TODO: Implement Pipedrive API attachment upload
        logger.info(
            f"[ImageStorage] CRM upload requested: "
            f"lead_id={crm_lead_id}, image={image_url}"
        )

        # Placeholder für Pipedrive Integration
        logger.warning(
            "[ImageStorage] CRM upload not yet implemented - "
            "Pipedrive API integration pending"
        )
        return False

    async def cleanup_old_images(
        self,
        max_age_days: int = 30,
        keep_approved: bool = True,
    ) -> int:
        """
        Bereinige alte Bilder aus generated_images/.

        Args:
            max_age_days: Maximales Alter in Tagen
            keep_approved: Behalte approved Bilder (aus docs/)

        Returns:
            Anzahl gelöschter Dateien
        """
        logger.info(
            f"[ImageStorage] Cleanup: max_age={max_age_days} days, "
            f"keep_approved={keep_approved}"
        )

        deleted_count = 0
        cutoff_date = datetime.now().timestamp() - (max_age_days * 86400)

        try:
            for filepath in self.generated_images_dir.glob("*.png"):
                # Skip if file is recent
                if filepath.stat().st_mtime > cutoff_date:
                    continue

                # Check if file is approved (exists in docs/)
                if keep_approved:
                    # Simple check: if filename appears in any session docs
                    is_approved = any(
                        self.docs_dir.glob(f"*/{filepath.name}")
                    )
                    if is_approved:
                        logger.debug(f"[ImageStorage] Keeping approved: {filepath.name}")
                        continue

                # Delete file
                filepath.unlink()
                deleted_count += 1
                logger.debug(f"[ImageStorage] Deleted: {filepath.name}")

            logger.info(f"[ImageStorage] Cleanup complete: {deleted_count} files deleted")
            return deleted_count

        except Exception as e:
            logger.error(f"[ImageStorage] Cleanup failed: {e}", exc_info=True)
            return deleted_count

    async def get_session_images(
        self,
        session_id: str,
    ) -> list[dict]:
        """
        Hole alle Bilder für eine Session.

        Args:
            session_id: Session ID

        Returns:
            Liste von Bild-Infos (path, url, type, approved)
        """
        images = []
        session_docs_dir = self.docs_dir / session_id

        if not session_docs_dir.exists():
            logger.info(f"[ImageStorage] No docs found for session: {session_id}")
            return images

        try:
            for filepath in session_docs_dir.glob("*.png"):
                images.append({
                    "path": str(filepath),
                    "filename": filepath.name,
                    "size_bytes": filepath.stat().st_size,
                    "created_at": datetime.fromtimestamp(
                        filepath.stat().st_ctime
                    ).isoformat(),
                })

            logger.info(
                f"[ImageStorage] Found {len(images)} images for session {session_id}"
            )
            return images

        except Exception as e:
            logger.error(f"[ImageStorage] Get session images failed: {e}", exc_info=True)
            return images


# Singleton instance
_storage_manager: Optional[ImageStorageManager] = None


def get_storage_manager() -> ImageStorageManager:
    """Get or create ImageStorageManager singleton."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = ImageStorageManager()
    return _storage_manager
