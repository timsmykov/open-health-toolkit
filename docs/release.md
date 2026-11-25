# Release checks

The initial release is a toolkit for operators who supply their own private files and accounts. The core installs from a clean checkout. The automated tests cover food lookup, calculations, score boundaries, diary snapshots, Oura pagination and coverage, and page-image preservation for a synthetic PDF.

## Before publishing

- Review the independent history and confirm the MIT license for the software. Keep the BLS CC BY 4.0 attribution with distributed copies.
- Run the documented quick start from a clean clone, verify the packaged reference data and scan tracked files and archive contents for secrets and personal records.
- Create a new repository for the toolkit. Publish only this repository and its independent history.
- State which integrations rely on the user's deployment. GitHub CI is defined in the repository. Real-account OAuth, search indexing, agent permission setup and scheduled deliveries are deployment checks.

## Further development

- Add independently licensed nutrient sources with field-level attribution and comparable food forms.
- Add reviewed composition fields to user product cards for better score coverage.
- Wire tested OpenBot and G-Brain adapters into a clean deployment with the operator's accounts.
- Add diary amendments and scheduled synchronization when those features are needed by an installation.
- Improve mixed-page OCR and illustrated retrieval using intentionally shareable fixtures.
