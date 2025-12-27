#!/usr/bin/env python3
from backend.settings import get_settings


def main() -> None:
    settings = get_settings(force_reload=True)
    print("IMAGE_PROVIDER=", settings.image_provider)
    print("GCP_PROJECT=", settings.gcp_project or "<unset>")
    print("GCP_LOCATION=", settings.gcp_location)
    print("IMAGEN_MODEL=", settings.imagen_model)
    print("GOOGLE_APPLICATION_CREDENTIALS=", settings.credentials_path or "<unset>")
    has_file = settings.credentials_file_exists()
    has_inline = settings.credentials_info() is not None
    print("Credentials file exists:", has_file)
    print("Inline credentials provided:", has_inline)
    print("Imagen ready:", settings.imagen_ready())


if __name__ == "__main__":
    main()
