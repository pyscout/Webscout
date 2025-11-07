# AI-Powered Changelog Generation with Free APIs

This document explains how the automated changelog generation using free AI APIs works in our release workflow.

## Overview

The `release-with-changelog.yml` workflow has been enhanced to automatically generate high-quality changelogs using **free AI providers** - specifically Pollinations.ai through the webscout package. This provides detailed, well-formatted, and informative release notes **without requiring any API keys or paid subscriptions**.

## How It Works

### 1. Primary Method: AI-Generated (Pollinations.ai)

When creating a new release, the workflow first attempts to generate a changelog using Pollinations.ai, a free AI service:

- **Provider**: Pollinations.ai (via webscout's TextPollinationsAI)
- **Model Used**: openai (free tier from Pollinations)
- **API Endpoint**: `https://text.pollinations.ai/openai`
- **Authentication**: None required - completely free!
- **Rate Limits**: Generous free tier, suitable for release workflows

#### Process Flow:

1. **Setup Python Environment**: Installs Python 3.11
2. **Install Dependencies**: Installs webscout package from the repository
3. **Collect Commit History**: Fetches all commits between the previous tag and HEAD
4. **Prepare Context**: Formats commit messages with short SHA hashes
5. **AI Generation**: Uses webscout's TextPollinationsAI provider to generate changelog with:
   - Brief release summary
   - Categorized changes (Features, Bug Fixes, Maintenance, Documentation, Performance, Security)
   - Emoji icons for visual appeal
   - Statistics (commit count)
   - Installation instructions
6. **Save Output**: Writes the generated changelog to `RELEASE_NOTES.md`

### 2. Fallback Method: Manual Changelog Extraction

If AI generation fails (API unavailable, network issues, timeout), the workflow automatically falls back to:

1. **Primary Fallback**: Extract from `changelog.md` file (if exists and contains the version)
   - Handles UTF-16 encoding automatically
   - Looks for version-specific sections
2. **Secondary Fallback**: Generate basic changelog from git commit history

This ensures releases are never blocked by AI service availability.

## Benefits of AI-Generated Changelogs

1. **Completely Free**: No API keys or subscriptions needed
2. **Better Formatting**: Consistently well-structured and professional
3. **Intelligent Categorization**: Automatically groups related changes
4. **Enhanced Readability**: Uses emojis and markdown formatting effectively
5. **Context-Aware**: Understands commit messages and creates meaningful summaries
6. **Time-Saving**: No manual changelog maintenance required
7. **Self-Hosted AI**: Uses the webscout package from the same repository

## Workflow Integration Points

### Step: `Set up Python for changelog generation`
- Sets up Python 3.11 environment

### Step: `Install webscout for AI changelog generation`
- Installs curl-cffi and requests dependencies
- Installs webscout package from the repository itself

### Step: `Generate changelog with AI (Pollinations.ai)`
- **ID**: `ai_changelog`
- **Continues on Error**: Yes (uses `continue-on-error: true`)
- **Output**: Sets `success` flag
- **Python Script**: Creates and executes a temporary Python script

### Step: `Extract changelog from changelog.md`
- **ID**: `changelog`
- **Condition**: Only runs if AI step failed
- **Fallback Logic**: Tries changelog.md, then git log
- **Encoding Support**: Handles UTF-16 encoded changelog.md files

### Step: `Set final changelog output`
- **ID**: `final_changelog`
- **Purpose**: Consolidates changelog from either AI or fallback method

## Configuration

### AI Model Configuration

The current configuration uses Pollinations.ai with these settings:
```python
TextPollinationsAI(
    model="openai",              # Free OpenAI-compatible model
    is_conversation=False,       # Single-shot generation
    timeout=60,                  # 60 second timeout
    system_prompt="..."          # Professional technical writer persona
)
```

### Available Models

Pollinations.ai offers multiple free models that can be used:
- `openai` - General purpose, good for changelogs (current)
- `openai-fast` - Faster responses
- `gemini` - Google's model
- `mistral` - Mistral AI model
- `deepseek-reasoning` - Advanced reasoning

To change the model, edit the `model` parameter in the Python script.

### Prompt Engineering

The prompt instructs the AI to:
- Act as a professional technical writer
- Generate detailed, engaging changelogs
- Use specific categories and emoji conventions
- Include installation instructions
- Maintain consistent markdown formatting
- Focus on clarity and informativeness

## Why Pollinations.ai?

1. **No Authentication**: No API keys, tokens, or authentication required
2. **Free & Unlimited**: No cost, generous rate limits for our use case
3. **Reliable**: Well-maintained service with good uptime
4. **OpenAI-Compatible API**: Standard chat completion format
5. **Quality Output**: Produces high-quality, coherent text
6. **Webscout Integration**: Already part of our package ecosystem

## Monitoring and Debugging

### Success Indicators
- Look for `✅ Successfully generated changelog with AI (Pollinations.ai)` in logs
- Check `RELEASE_NOTES.md` artifact for generated content

### Fallback Indicators
- Warning message: `⚠️ AI changelog generation failed, will use fallback method`
- Fallback message: `📝 Falling back to traditional changelog extraction...`

### Troubleshooting

If AI generation consistently fails:

1. **Check Webscout Installation**: Ensure webscout and dependencies install correctly
2. **Network Connectivity**: Verify GitHub Actions runner can reach text.pollinations.ai
3. **Dependency Issues**: Check curl-cffi compatibility with the runner OS
4. **Timeout Issues**: May need to increase timeout value (currently 60s)
5. **API Changes**: Pollinations.ai may have updated their API

The workflow will always complete successfully using fallback methods.

## Alternative Free Providers

If Pollinations.ai becomes unavailable, webscout offers many other free providers:

- **ChatSandbox**: Free OpenAI-compatible API
- **Cloudflare**: Workers AI (free tier)
- **DeepInfra**: Free tier with multiple models
- **Phind**: Code-focused AI (free)
- **Others**: Check webscout/Provider/ for more options

To switch providers, modify the Python script to import and use a different provider class.

## Future Enhancements

Potential improvements to consider:

1. **Multiple Provider Fallbacks**: Try several free APIs before falling back to manual
2. **Model Selection**: Make the AI model configurable via workflow inputs
3. **Custom Prompts**: Allow repository-specific prompt customization
4. **Multi-Language**: Generate changelogs in multiple languages
5. **Breaking Changes Detection**: Automatically highlight breaking changes
6. **PR Linking**: Enhanced linking to pull requests and issues
7. **Contributor Recognition**: Automatic contributor mentions and statistics
8. **Caching**: Cache AI responses to reduce API calls

## Security Considerations

- Uses free, public AI services (no sensitive data exposure concern)
- No API keys required (no secret management needed)
- Commit history is already public information
- Webscout package installed from the same repository (trusted source)
- Python script created in /tmp (automatically cleaned up)
- No external dependencies beyond curl-cffi and requests

## Backward Compatibility

The enhanced workflow is fully backward compatible:

- Existing `changelog.md` files still work as fallback
- Manual triggers still supported via `workflow_dispatch`
- No changes to release creation process
- Existing releases are not affected
- Works even if AI service is down (fallback methods)

## Cost Comparison

| Solution | Cost | API Key Required | Rate Limits |
|----------|------|------------------|-------------|
| GitHub Copilot API | $10-40/month | Yes | Varies by tier |
| OpenAI API | Pay per token | Yes | Varies by tier |
| Pollinations.ai | **FREE** | **No** | Generous |
| Webscout Providers | **FREE** | **No** | Varies by provider |

## Resources

- [Pollinations.ai Website](https://pollinations.ai/)
- [Webscout GitHub Repository](https://github.com/pyscout/Webscout)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Keep a Changelog](https://keepachangelog.com/)

