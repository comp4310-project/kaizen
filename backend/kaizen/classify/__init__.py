"""Labels de-identified comments with sentiment, HCAT categories, stage and urgency (FR3)."""

import os

# LiteLLM downloads its model list from GitHub on import unless told to use the copy it
# ships with. The bundled copy keeps runs and tests the same offline.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
