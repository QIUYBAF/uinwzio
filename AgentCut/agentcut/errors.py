from __future__ import annotations

import json


class AgentCutError(RuntimeError):
    def __init__(self, code: str, message: str, **context):
        self.code = code
        self.message = message
        self.context = context
        super().__init__(message)

    def as_dict(self):
        return {"error": self.code, "message": self.message, "context": self.context}

    def __str__(self):
        return json.dumps(self.as_dict(), ensure_ascii=False)
