#!/bin/bash

echo "🔐 Hive GitHub Secrets Setup"
echo "============================"
echo ""
echo "This script will help you add secrets to your GitHub repository."
echo "The secrets will be encrypted and only accessible during GitHub Actions runs."
echo ""

# Check if gh is authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ GitHub CLI not authenticated. Run: gh auth login"
    exit 1
fi

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Repository: $REPO"
echo ""

# Function to add a secret
add_secret() {
    local SECRET_NAME=$1
    local PROMPT_TEXT=$2

    echo -n "$PROMPT_TEXT: "
    read -s SECRET_VALUE
    echo ""

    if [ ! -z "$SECRET_VALUE" ]; then
        echo "$SECRET_VALUE" | gh secret set "$SECRET_NAME" -R "$REPO"
        echo "✅ Added $SECRET_NAME"
    else
        echo "⏭️  Skipped $SECRET_NAME"
    fi
}

echo "Enter your API keys (or press Enter to skip):"
echo "----------------------------------------------"

# Core AI APIs
add_secret "OPENAI_API_KEY" "OpenAI API Key"
add_secret "ANTHROPIC_API_KEY" "Anthropic/Claude API Key"
add_secret "GOOGLE_API_KEY" "Google API Key"
add_secret "GEMINI_API_KEY" "Gemini API Key"

# Airtable
add_secret "AIRTABLE_API_KEY" "Airtable API Key"
add_secret "AIRTABLE_BASE" "Airtable Base ID"

# MCP Servers
add_secret "BROWSERBASE_API_KEY" "Browserbase API Key"
add_secret "BROWSERBASE_PROJECT_ID" "Browserbase Project ID"
add_secret "MAGIC_API_KEY" "21st.dev Magic API Key"
add_secret "LINKUP_API_KEY" "Linkup API Key"
add_secret "EXA_API_KEY" "Exa API Key"
add_secret "FIRECRAWL_API_KEY" "Firecrawl API Key"
add_secret "OPIK_API_KEY" "Opik API Key"

# Other services
add_secret "TELEGRAM_BOT_TOKEN" "Telegram Bot Token"
add_secret "TELEGRAM_ADMIN_BOT_TOKEN" "Telegram Admin Bot Token"
add_secret "UNSPLASH_API_KEY" "Unsplash API Key"
add_secret "OPENWEATHER_API_KEY" "OpenWeather API Key"
add_secret "GMAPS_API_KEY" "Google Maps API Key"
add_secret "SEARCH_ENGINE_ID" "Google Search Engine ID"
add_secret "GOOGLE_CLIENT_ID" "Google OAuth Client ID"
add_secret "GOOGLE_CLIENT_SECRET" "Google OAuth Client Secret"

echo ""
echo "✅ GitHub Secrets setup complete!"
echo ""
echo "To view your secrets, go to:"
echo "https://github.com/$REPO/settings/secrets/actions"
echo ""
echo "Note: Secrets are encrypted and cannot be viewed once set."
echo "You can only update or delete them."
