# brazil-goias-law (gitlaw-scraper-dell, 2026-10-30)

Private. Source: Legisla Goiás (legisla.casacivil.go.gov.br, Secretaria de Estado da Casa Civil), a Vue app over a JSON
API: api/v2/pesquisa/legislacoes/constituicao_estadual and api/v2/pesquisa/legislacoes/<id> (field "conteudo" = compiled
Word HTML); list: api/v2/pesquisa/legislacoes?tipo_legislacao=1,15,21. Gate: pass (robots.txt answers the app page, no
rules; no challenge; the site offers its records as "Dados Abertos"). norma.casacivil.go.gov.br timed out (not used).
- Done: Constituição (10-constituicao) + 198 Leis Complementares (20-lc-01..05; Em Vigor / Revogada parcialmente /
  Promulgada; 3 altered with undated notes left out). All PUBLISHed; main 9912ac9 (200 commits). Claim deleted.
- Rules: earlier wordings = struck (<s>/<strike>/line-through) or red runs (nearest colour wins, as a browser shows it);
  notes = Arial Black runs, green "Vide" runs, <nota> elements and lines starting "- Redação/Acrescido/Revogado...".
  Unaltered act = as enacted, dated by its first D.O. (diarios_estaduais); altered = text in force only, credited to the
  Casa Civil, dated by the latest date its alteration notes cite ("Vide" excluded). Struck text in an act with no note
  is the act's own rendering of what it deletes (amending acts' annexes): left out, act given as enacted.
- Quirk: ADT art. 1 is printed "Art. 11º"; adt-0011 holds ADT arts 1, 3-10 (README Limits says so).
- fetch.py (one process, 3 s apart) PID 54988 finished. Next: Leis Ordinárias (tipo 2/16/20), Emendas Constitucionais.
