# Project Rename Refactoring Plan

## Session Information
- **Started:** 2025-12-22
- **Objective:** Rename project from "timemachine-py" to "omega-13"
- **Reference:** Galaxy Quest's Omega-13 time-rewind device (13 seconds)

## Naming Strategy
- **Display/Branding:** "Omega-13" (with hyphen)
- **Code/Python:** "omega13" (no separator)
- **Root Directory:** "omega-13" (with hyphen)

## Progress Tracking

### Phase 1: Python Package Renaming
- [ ] 1.1 Rename package directory `src/timemachine/` → `src/omega13/`
- [ ] 1.2 Update pyproject.toml
- [ ] 1.3 Update import statements
- [ ] 1.4 Update path constants
- [ ] 1.5 Update class names and JACK client
- [ ] 1.6 Update module docstrings

### Phase 2: Documentation Updates
- [ ] 2.1 Update README.md (add Galaxy Quest section, update all references)
- [ ] 2.2 Update docs/QUICKSTART.md
- [ ] 2.3 Update docs/TRANSCRIPTION.md
- [ ] 2.4 Update docs/BUILD.md

### Phase 3: Root Directory Rename
- [ ] 3.1 Rename root directory

### Phase 4: Git Operations
- [ ] 4.1 Commit changes
- [ ] 4.2 Update git remote (if needed)

### Phase 5: Verification
- [ ] 5.1 Test pip install
- [ ] 5.2 Verify CLI command
- [ ] 5.3 Test application launch
- [ ] 5.4 Verify path creation
- [ ] 5.5 Check JACK client name

## Files Modified
(Will be updated as refactoring progresses)

## Notes
- Keep Steve Harris attribution in documentation
- This is a breaking change (consider version 3.0.0)
- User config will need migration
