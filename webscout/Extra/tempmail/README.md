<div align="center">
  <a href="https://github.com/pyscout/Webscout">
    <img src="https://img.shields.io/badge/WebScout-TempMail%20Toolkit-blue?style=for-the-badge&logo=maildotru&logoColor=white" alt="WebScout TempMail Toolkit">
  </a>

  <h1>📧 TempMail</h1>

  <p><strong>Powerful Temporary Email Generation & Management</strong></p>

  <p>
    Create disposable email addresses, manage messages, and automate email verification workflows with multiple providers and both synchronous and asynchronous APIs.
  </p>

  <!-- Badges -->
  <p>
    <a href="https://pypi.org/project/webscout/"><img src="https://img.shields.io/pypi/v/webscout.svg?style=flat-square&logo=pypi&label=PyPI" alt="PyPI Version"></a>
    <a href="#"><img src="https://img.shields.io/badge/No%20API%20Key-Required-success?style=flat-square" alt="No API Key Required"></a>
    <a href="#"><img src="https://img.shields.io/badge/Python-3.7%2B-blue?style=flat-square&logo=python" alt="Python Version"></a>
  </p>
</div>

> [!NOTE]
> TempMail provides disposable email addresses for testing, verification, and privacy protection. It supports multiple providers and offers both synchronous and asynchronous interfaces.

## ✨ Key Features

### Email Management

* **Multiple Provider Support**
  * Native integration with Mail.TM and TempMail.io services
  * Extensible architecture for adding new providers
  * Consistent interface across all providers

* **Privacy Protection**
  * Generate disposable email addresses on demand
  * Protect your primary inbox from spam
  * Automatic cleanup after use

### Developer Experience

* **Dual API Support**
  * Synchronous interface for simple scripts
  * Asynchronous interface for high-performance applications
  * Complete feature parity between both interfaces

* **Automation Tools**
  * Helper utilities for common workflows
  * Email verification automation
  * Message waiting and processing

* **Command Line Interface**
  * Direct terminal access to all features
  * Real-time message monitoring
  * Simple and detailed output modes

## 🚀 Installation

Install or update Webscout to get access to the TempMail module:

```bash
pip install -U webscout
```

## 🖥️ Usage

### Basic Synchronous Example

```python
from webscout.Extra.tempmail import get_random_email

# 1. Create a new temporary email (provider chosen automatically)
email, provider = get_random_email()
print(f"[*] Your temporary email: {email}")
print(f"[*] Provider: {type(provider).__name__}")

try:
    # 2. Check for incoming messages
    print("[*] Waiting for messages...")
    # Add a small delay or implement a loop if checking immediately
    import time
    time.sleep(10)

    messages = provider.get_messages()
    if not messages:
        print("[*] No messages received yet.")
    else:
        print(f"[*] Received {len(messages)} message(s):")
        for i, message in enumerate(messages):
            print(f"\n--- Message {i+1} ---")
            print(f"  From: {message.get('from', 'N/A')}")
            print(f"  Subject: {message.get('subject', 'N/A')}")
            # Optionally print body, be mindful of length
            # print(f"  Body: {message.get('body', 'N/A')[:100]}...")

finally:
    # 3. Clean up: Delete the account/email when done
    print("[*] Deleting temporary email account...")
    provider.delete_account() # Adjust based on provider (delete_account or delete_email)
    print("[*] Account deleted.")

```

### Choosing a Specific Provider

```python
from webscout.Extra.tempmail import get_provider

# Use Mail.TM (default if unspecified in get_random_email)
print("[*] Using Mail.TM Provider")
mailtm_provider = get_provider("mailtm")
# MailTM typically uses create_account() which generates email+token
account_info = mailtm_provider.create_account()
print(f"[*] Mail.TM Email: {account_info['address']}")
# ... use mailtm_provider.get_messages(), etc. ...
mailtm_provider.delete_account(account_info['id'], account_info['token']) # Requires ID and Token for deletion
print("[*] Mail.TM account deleted.")


# Use TempMail.io
print("\n[*] Using TempMail.io Provider")
tempmailio_provider = get_provider("tempmailio")
# TempMail.io might have a different creation flow (check implementation)
# Assuming it also uses create_account() that returns an email address
email_info = tempmailio_provider.create_account() # Adapt if method/return differs
temp_email_io_addr = email_info # Adjust based on actual return value
print(f"[*] TempMail.io Email: {temp_email_io_addr}")
# ... use tempmailio_provider.get_messages(), etc. ...
tempmailio_provider.delete_account() # Adapt if deletion needs specific info
print("[*] TempMail.io account deleted.")
```

### Asynchronous API Example

```python
import asyncio
from webscout.Extra.tempmail import get_provider

async def manage_temp_email_async():
    # 1. Get an async provider instance (e.g., Mail.TM)
    provider = get_provider("mailtm", async_provider=True)
    await provider.initialize() # Important for async providers
    print("[*] Async Provider Initialized (Mail.TM)")

    try:
        # 2. Create a new email (async method)
        # Note: Method might be create_email or create_account depending on provider
        email_data = await provider.create_email() # Adjust if method/return differs
        email = email_data['address'] # Adjust based on actual return keys
        token = email_data.get('token') # Get token if applicable
        email_id = email_data.get('id') # Get ID if applicable
        print(f"[*] Your temporary email: {email}")

        # 3. Check for messages (async method)
        print("[*] Waiting for messages (async)...")
        await asyncio.sleep(15) # Wait a bit for potential incoming mail

        messages = await provider.get_messages()
        if not messages:
            print("[*] No messages received yet.")
        else:
            print(f"[*] Received {len(messages)} message(s):")
            for i, message in enumerate(messages):
                print(f"\n--- Message {i+1} ---")
                print(f"  From: {message.get('from', 'N/A')}")
                print(f"  Subject: {message.get('subject', 'N/A')}")

    finally:
        # 4. Clean up (async methods)
        print("[*] Deleting temporary email (async)...")
        # Deletion method and required arguments depend on the provider
        if token and email_id:
            await provider.delete_email(email_id, token) # Example for MailTM-like
        elif hasattr(provider, 'delete_email') and not token and not email_id:
             await provider.delete_email(email) # Example if only email needed
        else:
            print("[!] Could not determine deletion method/parameters. Manual cleanup might be needed.")

        await provider.close() # Close the underlying HTTP client
        print("[*] Provider closed.")

# Run the async function
if __name__ == "__main__":
    asyncio.run(manage_temp_email_async())
```

### Command Line Interface (CLI)

Access temporary email features directly from your terminal:

```bash
python -m webscout.Extra.tempmail.cli --help
```

**Example: Get a temp email and watch for messages:**

```bash
# This will generate an email and check for new messages every 15 seconds
python -m webscout.Extra.tempmail.cli --wait 15
```

**CLI Options:**

*   `--provider {mailtm,tempmailio}`: Specify the provider to use (default: mailtm).
*   `--wait SECONDS`: Wait time in seconds between checking for new messages (default: 10). Set to 0 to check once and exit.
*   `--output {simple,detailed}`: Control the level of detail in the output (default: simple). `detailed` usually shows message bodies.

## 📚 API Reference

The module is built around abstract base classes for providers, ensuring a consistent interface.

### Base Abstract Classes

*   `TempMailProvider`: Defines the interface for synchronous temporary email providers.
*   `AsyncTempMailProvider`: Defines the interface for asynchronous temporary email providers.

### Provider Implementations

#### Mail.TM

*   **`MailTM`**: Synchronous client for the Mail.TM service.
*   **`MailTMAsync`**: Asynchronous client for the Mail.TM service.

#### TempMail.io

*   **`TempMailIO`**: Synchronous client for the TempMail.io service.
*   **`TempMailIOAsync`**: Asynchronous client for the TempMail.io service.

### Factory Functions

*   **`get_provider(provider_name: str, async_provider: bool = False) -> Union[TempMailProvider, AsyncTempMailProvider]`**:
    Retrieves an initialized provider instance based on its name (`'mailtm'` or `'tempmailio'`) and whether an async version is needed.
*   **`get_random_email(provider_name: Optional[str] = None) -> Tuple[str, TempMailProvider]`**:
    Generates a random email address using either the specified provider or a randomly selected one. Returns the email address and the synchronous provider instance.
*   **`get_disposable_email()`**: An alias for `get_random_email()`.

### Asynchronous Utilities (`webscout.Extra.tempmail.async_utils`)

*   **`AsyncTempMailHelper`**: A helper class simplifying common asynchronous operations like email creation and message waiting.
*   **`get_temp_email(alias: Optional[str] = None, domain: Optional[str] = None) -> Tuple[str, AsyncTempMailHelper]`**:
    Asynchronously creates a temporary email using the helper. Returns the email address and the helper instance.
*   **`wait_for_message(helper: AsyncTempMailHelper, timeout: int = 60, check_interval: int = 5) -> Optional[dict]`**:
    Asynchronously waits for a message to arrive for the email managed by the `helper`. Returns the message dictionary or `None` if timeout occurs.

##  Advanced Usage Examples

### Automated Email Verification Workflow (Async)

```python
import asyncio
from webscout.Extra.tempmail import get_provider
# Assume extract_link_from_message is defined elsewhere
# from your_parsing_utils import extract_link_from_message

async def verify_email_signup(service_url, username):
    """
    Attempts to sign up for a service using a temp email and
    retrieve the verification link.
    """
    provider = get_provider("mailtm", async_provider=True)
    await provider.initialize()
    print(f"[*] Initialized async provider for {service_url} signup")

    email_data = None
    verification_link = None

    try:
        email_data = await provider.create_email()
        email = email_data['address']
        print(f"[*] Generated temp email: {email} for {username}")

        # --- Placeholder for your signup logic ---
        print(f"[*] Attempting signup on {service_url} with {email}...")
        # success = await sign_up_to_service(service_url, username, email)
        success = True # Assume signup initiates email sending
        if not success:
             print("[!] Service signup failed.")
             return None
        # -----------------------------------------

        print("[*] Waiting for verification email...")
        # Wait up to 2 minutes (12 checks * 10 seconds interval)
        for attempt in range(12):
            print(f"[*] Checking for messages (Attempt {attempt + 1}/12)...")
            messages = await provider.get_messages()

            # Simple check: look for "verify" or "confirm" in subject
            verification_msg = next((
                m for m in messages
                if "verify" in m.get('subject', '').lower() or \
                   "confirm" in m.get('subject', '').lower()
            ), None)

            if verification_msg:
                print("[+] Verification email found!")
                print(f"  Subject: {verification_msg.get('subject')}")
                # --- Placeholder for link extraction ---
                # verification_link = extract_link_from_message(verification_msg.get('body', ''))
                verification_link = f"http://example.com/verify?token=xyz..." # Dummy link
                # -------------------------------------
                if verification_link:
                    print(f"[+] Extracted verification link: {verification_link}")
                    break # Exit loop once link is found
                else:
                    print("[!] Found email, but failed to extract link.")

            await asyncio.sleep(10) # Wait before next check

        if not verification_link:
            print("[!] Timed out waiting for verification email or link.")

    except Exception as e:
        print(f"[!] An error occurred: {e}")
    finally:
        # Clean up regardless of success/failure
        if email_data:
            print("[*] Cleaning up temporary email...")
            try:
                # Adjust deletion based on provider needs (ID, token, etc.)
                await provider.delete_email(email_data['id'], email_data['token'])
                print("[*] Temporary email deleted.")
            except Exception as del_e:
                print(f"[!] Error during email deletion: {del_e}")

        await provider.close()
        print("[*] Async provider closed.")

    return verification_link

# Example call (replace with actual service interaction)
# asyncio.run(verify_email_signup("https://some-service.com/signup", "testuser123"))
```

### Testing Email Functionality (Sync)

```python
from webscout.Extra.tempmail import get_random_email
import time
# Assume send_test_email is a function you have defined
# from your_email_sending_module import send_test_email

def test_email_sending_feature():
    """Tests if an email sent to a temp address is received."""
    print("[*] Starting email sending test...")
    email, provider = get_random_email()
    print(f"[*] Generated temp email for receiving: {email}")

    test_subject = "My Test Email Subject"
    test_content = "This is the body of the test email."
    test_email_received = False

    try:
        # --- Placeholder for your email sending logic ---
        print(f"[*] Sending test email to {email}...")
        # success = send_test_email(email, test_subject, test_content)
        success = True # Assume sending works
        if not success:
            print("[!] Failed to send test email.")
            return False
        # ---------------------------------------------

        print("[*] Waiting a few seconds for email delivery...")
        time.sleep(15) # Allow time for email to arrive

        print("[*] Checking inbox...")
        messages = provider.get_messages()

        if not messages:
            print("[!] No messages received in the temporary inbox.")
        else:
            print(f"[*] Received {len(messages)} message(s). Checking for test email...")
            for msg in messages:
                if msg.get('subject') == test_subject:
                    print(f"[+] Test email received successfully!")
                    print(f"  From: {msg.get('from')}")
                    # Optional: Verify content
                    # if test_content in msg.get('body', ''):
                    #    print("[+] Email content verified.")
                    test_email_received = True
                    break # Found the email
            if not test_email_received:
                print(f"[!] Test email with subject '{test_subject}' not found.")

    except Exception as e:
        print(f"[!] An error occurred during the test: {e}")
    finally:
        # Clean up the temporary email account
        print("[*] Deleting temporary email account...")
        try:
            provider.delete_account() # Adjust if deletion needs specific info
            print("[*] Account deleted.")
        except Exception as del_e:
            print(f"[!] Error deleting account: {del_e}")

    print(f"[*] Email sending test result: {'Success' if test_email_received else 'Failure'}")
    return test_email_received

# Run the test
# test_result = test_email_sending_feature()
```

### Using Async Helper Utilities

```python
import asyncio
from webscout.Extra.tempmail.async_utils import get_temp_email, wait_for_message

async def use_async_helpers():
    email = None
    helper = None
    print("[*] Using async helper utilities...")
    try:
        # 1. Create a new email using the helper
        email, helper = await get_temp_email()
        print(f"[*] Temporary email created via helper: {email}")

        # 2. Wait for a message to arrive (timeout after 60 seconds)
        print("[*] Waiting for a message (up to 60s)...")
        # Simulate sending an email here if needed for testing
        # await send_email_to(email, "Helper Test", "Body content")

        message = await wait_for_message(helper, timeout=60, check_interval=5)

        if message:
            print("[+] Message received!")
            print(f"  From: {message.get('from', 'N/A')}")
            print(f"  Subject: {message.get('subject', 'N/A')}")
            # print(f"Body: {message.get('body', 'N/A')[:100]}...") # Optional: print body snippet
        else:
            print("[!] No messages received within the 60-second timeout period.")

    except Exception as e:
        print(f"[!] An error occurred: {e}")
    finally:
        # 3. Clean up using the helper's delete method
        if helper:
            print("[*] Cleaning up email via helper...")
            await helper.delete()
            print("[*] Email deleted by helper.")
        else:
            print("[!] Helper instance not available for cleanup.")

# Run the async function
if __name__ == "__main__":
    asyncio.run(use_async_helpers())
```

## 🔌 Provider Integration

Adding support for a new temporary email service is straightforward thanks to the abstract provider pattern used throughout Webscout:

1.  **Create Provider Classes**: Implement two new classes:
    *   One inheriting from `webscout.Extra.tempmail.base.TempMailProvider` for synchronous operations.
    *   One inheriting from `webscout.Extra.tempmail.base.AsyncTempMailProvider` for asynchronous operations.
    Implement all the abstract methods defined in the base classes (e.g., `create_account`/`create_email`, `get_messages`, `delete_account`/`delete_email`).
2.  **Register in Factory**: Update the `get_provider` function in `webscout/Extra/tempmail/base.py` to recognize a new `provider_name` string and return instances of your newly created classes.
3.  **Expose (Optional)**: If desired, update `webscout/Extra/tempmail/__init__.py` to directly import and expose your new provider classes for users who might want to instantiate them directly.
4.  **Add Tests**: Create unit and integration tests for your new provider to ensure it functions correctly.
5.  **Update Documentation**: Add your new provider to this README, including any specific usage notes.

## 🛠️ Implementation Details

*   **Parser**: Uses the `Scout` HTML/XML parser from the core `webscout` library instead of external libraries like `BeautifulSoup` for consistency and potentially better performance within the Webscout ecosystem.
*   **Sync/Async Parity**: Aims to provide feature parity between the synchronous (`TempMailProvider`) and asynchronous (`AsyncTempMailProvider`) interfaces for all supported providers.
*   **Factories**: Relies on factory functions (`get_provider`, `get_random_email`) for easy and consistent instantiation of provider objects.
*   **Minimal Dependencies**: Avoids adding external logging or unnecessary dependencies to ensure smooth integration into projects using Webscout.

## 🤝 Contributing

Contributions to enhance the TempMail module are highly welcome! Potential areas include:

1.  **Adding New Providers**: Integrating support for additional temporary email services.
2.  **Improving CLI**: Enhancing the command-line interface with more features or better output formatting.
3.  **Robustness**: Improving error handling, retries, and provider-specific edge cases.
4.  **Utility Functions**: Adding more helper functions for common temporary email automation tasks.
5.  **Documentation**: Refining examples, API descriptions, and usage guides.

Please refer to the main Webscout project's contributing guidelines if you plan to submit a pull request.

<div align="center">
  <!-- Footer Links (Mirrored from main README) -->
  <div>
    <a href="https://t.me/PyscoutAI"><img alt="Telegram Group" src="https://img.shields.io/badge/Telegram%20Group-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white"></a>
    <a href="https://t.me/ANONYMOUS_56788"><img alt="Developer Telegram" src="https://img.shields.io/badge/Developer%20Contact-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white"></a>
    <a href="https://buymeacoffee.com/oevortex"><img alt="Buy Me A Coffee" src="https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black"></a>
  </div>
  <p>📧 TempMail - Part of the Webscout Toolkit</p>
  <a href="https://github.com/pyscout/Webscout">Back to Main Webscout Project</a>
</div>