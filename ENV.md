# Environment & Keys

Manage credentials and model id without extra dependencies.

## Template

- Generate the template and copy to `.env`:

        python env_setup.py --write-template
        cp .env.template .env
        # edit .env to set OPENAI_API_KEY

- `.env.template` content:

    # .env.template — copy to .env and fill real values
    # REQUIRED
    OPENAI_API_KEY=sk-REPLACE_ME

    # OPTIONAL
    # Organization and project (if applicable to your OpenAI account)
    OPENAI_ORG=org-REPLACE_ME
    OPENAI_PROJECT=proj-REPLACE_ME

    # Model override (your ocr_batch_submit.py can read this if you wire it)
    MODEL_ID=gpt-5-thinking

## Loading

- At the top of `ocr_batch_submit.py`, we call:

        import env_setup
        env_setup.load_env_file(strict=False)

- Validate your `.env`:

        python env_setup.py --file .env --strict --print

- Override model per session:

        export MODEL_ID=gpt-5-thinking


---