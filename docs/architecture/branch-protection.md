# Required GitHub branch protection

CI workflow enforces phase/* PR origin. GitHub repository settings must additionally protect main with:
- pull requests required before merge
- required MITROS CI checks
- no direct pushes for normal development
- no force pushes
- stale approvals dismissed after new commits
- branch must be up to date before merge when required by repository policy

The phase workflow is the automation layer; repository branch protection is the enforcement layer.
