# Devolución completa del proyecto

Fecha: 2026-11-10
Proyecto: Vaya Job Board Indexer
Alcance revisado: Phase 0 y Phase 1
Estado: documentación de investigación completa; sin código de aplicación

> Nota: esta devolución corresponde a Phase 0/1. El estado actual de Phase 2 está en `docs/phase2_report.md`.

## 1. Dictamen general

**Phase 1 está aprobada con observaciones.** La investigación es honesta, ordenada y útil. La matriz de 78 plataformas, las notas de investigación, el informe de factibilidad y la arquitectura forman una base seria para empezar Phase 2.

Pero hay una diferencia importante entre **“investigado”** y **“funcionando”**. Hoy el proyecto tiene evidencia de investigación, no cobertura real. No hay código, conectores, tests, API, UI, demo ni deploy. Eso es esperable en Phase 1, pero significa que falta la mayor parte del trabajo del challenge.

Conclusión principal: **el proyecto es técnicamente viable como producto parcial y honesto; no es viable como cobertura 78/78 live-verified en 21 días con una sola persona.**

## 2. Qué se entregó y qué significa

Se crearon cuatro documentos:

- `docs/platform_matrix.csv`: 78 filas, 58 ATS + 20 job boards, 16 columnas.
- `docs/research_notes.md`: evidencia de endpoints, field mappings, pruebas HTTP y limitaciones.
- `docs/feasibility_report.md`: análisis de cobertura, esfuerzo, riesgos y GO/NO-GO.
- `docs/architecture.md`: diseño de monolito modular, contrato de conectores, deduplicación, cierre, scheduler, API y testing.

La matriz está bien validada: 78 filas exactas, sin duplicados, con la lista exacta de Vaya. Eso es un buen control de calidad.

## 3. Fortalezas

1. **Honestidad técnica.** La matriz usa `UNKNOWN` en lugar de inventar endpoints, tenants o resultados. Eso es clave para un challenge de datos.
2. **Evidencia real.** Hay 11 endpoints públicos que devolvieron datos en vivo: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Personio, Teamtailor, Pinpoint, Rippling y Workday.
3. **Buena separación entre investigación y cobertura.** El informe de factibilidad no confunde “research” con “implemented”.
4. **Arquitectura adecuada.** Monolito modular, SQLite, FTS5, worker simple, fetch runs y política conservadora de cierre. Es coherente con las restricciones de bajo costo y sin microservicios.
5. **Política correcta de fallos y cierres.** Un fetch fallido no cierra jobs. Eso es un requisito explícito del challenge y está bien resuelto en el diseño.
6. **Conciencia del long tail.** El informe reconoce que 43 plataformas son HTML-first y que eso domina el esfuerzo.
7. **Buen handoff conceptual.** La arquitectura y el coverage dashboard están pensados para que otro equipo pueda operar el sistema.

## 4. Debilidades y riesgos

1. **La matriz es un inventario, no una prueba de cobertura.** 48 de 78 filas tienen confianza baja. Eso no está mal, pero significa que el 61% de las plataformas todavía necesita investigación adicional antes de planificar un conector serio.
2. **Muchos campos críticos están en `UNKNOWN`.** En la matriz:
   - 65/78 no tienen paginación verificada.
   - 65/78 no tienen descripción verificada.
   - 65/78 no tienen application URL verificada.
   - 23/78 tienen autenticación desconocida.
   Eso muestra que la cobertura real está muy lejos de 78/78.
3. **Hay 6 plataformas bloqueadas y 1 no investigada.** Rival, eJobBoard, Nodex, JobBoardFire, CareerSiteCloud y JobMount están bloqueadas. FirstStage sigue sin identidad clara. No conviene gastar tiempo ahí hasta resolver acceso o producto.
4. **Las APIs autenticadas o Enterprise son un freno comercial.** JobKit, Jobboardly, Jobiqo, JBoard.io, SmartJobBoard, JobBoard.io, Wiley Madgex y Talenetic pueden requerir planes, contratos o credenciales que no están disponibles.
5. **Workday es una API no documentada.** El endpoint CXS funciona, pero puede cambiar sin aviso. Necesita fixture, monitoreo y plan de fallback.
6. **HTML-first es caro de mantener.** 43 plataformas HTML implican selectores frágiles, paginación distinta y posibles bloqueos. Sin fixtures y monitoreo, se rompen en silencio.
7. **Falta revisión legal/operativa.** No se relevaron robots.txt, términos de uso, licencias de descripciones ni retención de datos. Antes de escalar, hay que revisarlo.
8. **El plan de 21 días es optimista incluso para cobertura parcial.** El propio informe estima 43-70 días para el alcance completo. La diferencia con 21 días es de 2x a 3x.
9. **El README está vacío.** Para el submission final hace falta quickstart, dependencias, deploy, estado de cobertura, costos y limitaciones.
10. **No hay CI, lint, typecheck ni tests.** Es esperable en Phase 1, pero Phase 2 debería arrancar con eso desde el primer commit.

## 5. Lectura de los números

- **78 plataformas:** 58 ATS + 20 job boards.
- **71 `RESEARCHED`:** tienen al menos una fuente u homepage, pero no todas tienen endpoint verificado.
- **6 `ACCESS_BLOCKED`:** acceso fallido.
- **1 `NOT_RESEARCHED`:** FirstStage.
- **11 high confidence:** los únicos con evidencia live fuerte.
- **19 medium confidence:** hay página, docs o sample, pero falta verificación.
- **48 low confidence:** homepage o patrón no verificado.
- **13 feeds estructurados plausibles:** 9 JSON públicos, 1 JSON no verificado, 1 JSON no documentado, 1 XML y 1 RSS.
- **6 APIs autenticadas/contractuales:** no son viables sin acceso.
- **43 HTML-first:** el grueso del esfuerzo.

La conclusión de estos números es clara: **hay un núcleo de 11 conectores muy factible, un segundo anillo de 5-10 conectores razonable, y una cola larga de 40-50 plataformas que no entra en 21 días con una persona.**

## 6. Opinión sobre el proyecto

Mi opinión es positiva sobre la **calidad de la Phase 1**, pero cauta sobre la **viabilidad del objetivo completo**.

El proyecto tiene un problema de **alcance**, no de tecnología. La arquitectura propuesta es razonable y el núcleo de datos está bien pensado. Lo que hace difícil el challenge no es construir un indexador: es construir y mantener 78 integraciones heterogéneas, muchas sin API pública, algunas con autenticación Enterprise y otras con HTML frágil.

También creo que el challenge está diseñado para premiar **cobertura real y confiabilidad**, no una arquitectura elegante por sí sola. Un producto con 16-20 plataformas funcionando, evidencia live, deduplicación, cierres conservadores y un dashboard honesto puede ser más valioso que un “78/78” superficial lleno de conectores frágiles.

Dicho eso: si la condición de adquisición es **78/78 live-verified**, entonces el proyecto, tal como está planteado para 21 días y una persona, **no es factible**. Habría que ampliar el plazo, sumar gente o conseguir credenciales/planes Enterprise.

## 7. Conclusiones

1. **La Phase 1 cumplió su objetivo:** hay un mapa realista de las 78 plataformas y una arquitectura defendible.
2. **El núcleo técnico es viable:** 11 APIs públicas permiten construir un MVP creíble en pocos días.
3. **La cobertura total no es viable en el plazo actual:** la cola larga HTML y las APIs cerradas dominan el esfuerzo.
4. **La honestidad del informe es una fortaleza:** decir “NO-GO para 78/78” es mejor que prometer cobertura falsa.
5. **El mayor riesgo es el alcance, no la tecnología:** sin acotar, el proyecto se desordena y no llega a una demo sólida.
6. **El submission necesita producto, no solo research:** faltan código, tests, API, UI, demo, deploy y documentación de handoff.
7. **La estrategia correcta es coverage-first:** construir primero lo que tiene evidencia y dejar el resto como roadmap explícito.

## 8. Plan recomendado para 21 días

### Días 1-2: cierre de Phase 1

- Congelar alcance inicial: 11 conectores públicos + 4-6 HTML.
- Validar la matriz y el informe.
- Definir el modelo normalizado y el contrato de conectores.
- Crear `pyproject.toml`, estructura de `src/`, `tests/` y CI básico.

### Días 3-8: core y primeros seis conectores

- Implementar HTTP client, retries, rate limits y fetch runs.
- Implementar SQLite, migraciones y modelo normalizado.
- Implementar Greenhouse, Lever, Ashby, Workable, SmartRecruiters y Recruitee.
- Agregar fixtures y tests de contrato.
- Crear el coverage dashboard mínimo.

### Días 9-13: segundo anillo

- Implementar Personio, Teamtailor, Pinpoint, Rippling y Workday.
- Agregar JazzHR y Eightfold AI como HTML/JSON-LD si los fixtures son estables.
- Implementar extractor genérico de JSON-LD.
- Probar al menos un tenant por plataforma y dos donde sea posible.

### Días 14-18: producto

- Implementar búsqueda con SQLite FTS5.
- Implementar deduplicación conservadora.
- Implementar política de cierre con fetch failures separados.
- Implementar scheduler y observabilidad.
- Agregar API y UI mínima.
- Agregar JobBoardHQ, JobBoard.com, eJobSiteSoftware y Artha como samples HTML.

### Días 19-20: hardening y handoff

- Correr pruebas live multi-tenant.
- Revisar logs, errores y rate limits.
- Completar README, deploy, costos y limitaciones.
- Generar coverage checklist con evidencia.
- Congelar features.

### Día 21: submission

- Validación final.
- Demo.
- Envío.
- Sin trabajo nuevo de plataformas ese día.

Este plan produce un producto creíble, pero **no 78/78**. Para 78/78 yo pediría 6-10 semanas o 2-3 personas.

## 9. Si el objetivo es competir por los 78

Habría que agregar:

- Descubrimiento y validación de tenants.
- Framework genérico de extracción HTML/JSON-LD.
- Fixtures por plataforma y monitoreo de roturas.
- Credenciales o planes Enterprise para las APIs cerradas.
- Pruebas multi-tenant.
- Revisión de términos y robots.
- Dashboard de cobertura con evidencia.
- Proceso de revisión manual para deduplicación ambigua.

Sin esas piezas, un “78/78” sería una ilusión de cobertura.

## 10. GO / NO-GO

**GO** para Phase 2 con los 11 conectores públicos de alta confianza y un framework genérico.

**NO-GO** para afirmar cobertura completa 78/78 live-verified antes del 30 de noviembre en las condiciones actuales: una persona, repositorio vacío, sin credenciales Enterprise y 21 días.

La decisión más sana es construir el núcleo, entregar cobertura parcial con evidencia y ser explícito sobre lo que falta. Si el challenge exige 78/78 para adquirir, entonces hay que renegociar alcance, plazo o recursos.

## 11. Recomendaciones accionables por semana

### Semana 1

- Cerrar Phase 1 y congelar alcance.
- Crear esqueleto del proyecto y CI.
- Implementar HTTP client, rate limits, retries y fetch runs.
- Implementar modelo normalizado y SQLite.
- Implementar Greenhouse y Lever.
- Escribir fixtures y tests.

### Semana 2

- Implementar Ashby, Workable, SmartRecruiters y Recruitee.
- Implementar Personio y Teamtailor.
- Agregar coverage dashboard.
- Probar dos tenants por conector cuando sea posible.
- Revisar errores y tasas de éxito.

### Semana 3

- Implementar Pinpoint, Rippling y Workday.
- Agregar JazzHR, Eightfold AI y JobBoardHQ.
- Implementar búsqueda FTS5.
- Implementar deduplicación y cierre conservador.
- Agregar API y UI mínima.
- Preparar deploy y documentación.

### Semana 4

- Hardening.
- Pruebas live multi-tenant.
- Completar README y handoff.
- Congelar y enviar.

## 12. Anexo: 11 conectores priorizados

| Prioridad | Plataforma | Método | Endpoint verificado | Riesgo principal |
| ---: | --- | --- | --- | --- |
| 1 | Greenhouse | JSON público | `https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true` | Board token inválido. |
| 2 | Lever | JSON público | `https://api.lever.co/v0/postings/{company}?mode=json` | Company slug inválido. |
| 3 | Ashby | JSON público | `https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true` | Sin company name en el item. |
| 4 | Workable | JSON público | `https://apply.workable.com/api/v1/widget/accounts/{subdomain}?details=true` | Subdominio inválido. |
| 5 | SmartRecruiters | JSON público | `https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=1` | Slugs inválidos; descripción parcial. |
| 6 | Recruitee | JSON público | `https://{company}.recruitee.com/api/offers/` | Subdominio inválido. |
| 7 | Personio | XML público | `https://{company}.jobs.personio.de/xml?language=en` | Puede faltar application URL. |
| 8 | Teamtailor | RSS público | `https://{company}.teamtailor.com/jobs.rss` | Feed truncado. |
| 9 | Pinpoint | JSON público | `https://{company}.pinpointhq.com/postings.json` | Company slug inválido. |
| 10 | Rippling | JSON público | `https://ats.rippling.com/api/v2/board/{slug}/jobs?page=1` | Descripción parcial. |
| 11 | Workday | JSON no documentado | `POST https://{host}/wday/cxs/{tenant}/{site}/jobs` | API no documentada; detail fetch necesario. |

## 13. Anexo: plataformas bloqueadas o de alto riesgo

| Plataforma | Estado | Problema |
| --- | --- | --- |
| Rival | `ACCESS_BLOCKED` | El dominio no resuelve. |
| eJobBoard | `ACCESS_BLOCKED` | El dominio no resuelve; posiblemente discontinuada. |
| Nodex | `ACCESS_BLOCKED` | Sitio oficial devolvió 403. |
| JobBoardFire | `ACCESS_BLOCKED` | Sitio oficial devolvió 403. |
| CareerSiteCloud | `ACCESS_BLOCKED` | Sitio oficial devolvió 403. |
| JobMount | `ACCESS_BLOCKED` | Solo API de posting; sitio devolvió 403. |
| FirstStage | `NOT_RESEARCHED` | Identidad y superficie pública sin verificar. |
| BambooHR | Riesgo medio | Endpoint JSON público sin verificar. |
| WP Job Manager | Riesgo medio | REST del vendor devolvió 404; falta board real. |
| Niceboard | Riesgo medio | Patrón reportado, sin tenant live verificado. |
| Jobvite | Riesgo medio | Tests redirigieron a página genérica. |
| Eightfold AI | Riesgo medio | API devolvió 403; HTML disponible. |

## 14. Próximos pasos

1. Aprobar este documento y el alcance de Phase 2.
2. Crear el esqueleto del proyecto y CI.
3. Implementar los primeros seis conectores.
4. Medir cobertura real, no cobertura declarada.
5. Revisar el plan al final de la semana 1 con datos de ejecución.

La regla central para todo el proyecto: **no declarar cobertura sin evidencia live y sin pruebas multi-tenant.**
