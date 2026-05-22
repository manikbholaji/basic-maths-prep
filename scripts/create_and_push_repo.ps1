param(
    [string]$RepoName = "shapers_academic_advisor",
    [string]$Description = "Shapers Academic Advisor - Basic Maths Prep",
    [switch]$Private = $false,
    [string]$Branch = "main"
)

Write-Host "This script will create a new GitHub repository and push the current project to it. Requires 'gh' (GitHub CLI) and 'git' installed."

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI 'gh' not found. Install from https://cli.github.com/ and authenticate (gh auth login)."
    exit 1
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "'git' not found. Install Git and retry."
    exit 1
}

$repoVisibility = if ($Private) { 'private' } else { 'public' }

Write-Host "Creating repository '$RepoName' ($repoVisibility) on GitHub..."
$createArgs = @('repo','create',$RepoName,'--description',$Description,'--source','.',"--$repoVisibility","--push")

# If branch doesn't exist locally, create it
try {
    git rev-parse --verify $Branch > $null 2>&1
} catch {
    git checkout -b $Branch
}

# Create the repo and push (gh handles remote creation and push when --push provided)
gh repo create $RepoName --description "$Description" --$repoVisibility --source . --push --remote origin

Write-Host "Repository created and pushed. Next, deploy on Streamlit Cloud:"
Write-Host "1. Go to https://share.streamlit.io and sign in."
Write-Host "2. Click 'New app' → choose GitHub, select repository '$RepoName', branch '$Branch' and set 'App file' to 'app/basic_maths_app.py'."
Write-Host "3. In Streamlit app settings, set required secrets (if any) and enable privacy settings as needed."

Write-Host "Done. If you want the repository private, re-run with -Private."
