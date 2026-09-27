"""The four questions the dashboard asks the database.

They live here rather than inside the page, so each one can be read,
run by hand in psql, and tested without drawing anything.
"""

POR_DIA = """
SELECT DATE(aberto_em) AS dia, COUNT(*) AS n
FROM reclamacoes
WHERE aberto_em IS NOT NULL
GROUP BY 1
ORDER BY 1
"""

POR_BAIRRO = """
SELECT COALESCE(bairro, 'SEM BAIRRO') AS bairro, COUNT(*) AS n
FROM reclamacoes
GROUP BY 1
ORDER BY 2 DESC
"""

POR_TIPO = """
SELECT tipo, COUNT(*) AS n
FROM reclamacoes
WHERE tipo IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 15
"""

# Hours, not days: a complaint closed the same afternoon and one closed
# three weeks later both round to "days" in a way that hides the first.
TEMPO_ATE_FECHAR = """
SELECT COALESCE(bairro, 'SEM BAIRRO') AS bairro,
       COUNT(*) AS fechadas,
       ROUND(AVG(EXTRACT(EPOCH FROM (fechado_em - aberto_em)) / 3600)::numeric, 1)
           AS horas_media
FROM reclamacoes
WHERE fechado_em IS NOT NULL
  AND aberto_em IS NOT NULL
  AND fechado_em >= aberto_em
GROUP BY 1
ORDER BY 3 DESC
"""

PROBLEMAS = """
SELECT problema, COUNT(*) AS n
FROM problemas
GROUP BY 1
ORDER BY 2 DESC
"""

TODAS = {
    "por dia": POR_DIA,
    "por bairro": POR_BAIRRO,
    "por tipo": POR_TIPO,
    "tempo ate fechar": TEMPO_ATE_FECHAR,
    "problemas": PROBLEMAS,
}


def ask(connection, statement):
    """Run one query and return its column names and rows."""
    with connection.cursor() as cursor:
        cursor.execute(statement)
        names = [column[0] for column in cursor.description]
        return names, cursor.fetchall()
