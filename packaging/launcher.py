"""Entry point for the bundled, isolated Python interpreter."""
import os
from pathlib import Path
import sys

resources = Path(__file__).resolve().parent
certificate_bundle = resources / "python/lib/python3.13/site-packages/pip/_vendor/certifi/cacert.pem"
if not certificate_bundle.is_file():
    raise SystemExit("The application's bundled HTTPS certificate store is missing. Rebuild or reinstall the application.")
os.environ["SSL_CERT_FILE"] = str(certificate_bundle)
sys.path.insert(0, str(resources / "manager/src"))
from deadlock_mac.cli import main

raise SystemExit(main())
