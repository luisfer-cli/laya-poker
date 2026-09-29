import laya

agent = laya.load("convaiinnovations/laya")

state = {
    "subject": "Error en producción",
    "body": "La API devuelve 500 y varios usuarios están afectados."
}

questions = {
    "priority": {
        "type": "choice",
        "instructions": "¿Qué prioridad debería tener este incidente?",
        "criteria": {
            "low": "Problema menor sin impacto importante",
            "medium": "Impacto limitado",
            "high": "Servicio o usuarios seriamente afectados"
        }
    },
    "escalate": {
        "type": "noul",
        "instructions": "¿Este incidente debería escalarse?"
    }
}

result = agent.predict(state, questions)

print(result)
