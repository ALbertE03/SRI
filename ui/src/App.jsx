import { useEffect, useMemo, useRef, useState } from 'react'
import {
    Brain,
    CheckCircle,
    ChevronRight,
    ExternalLink,
    FileText,
    Globe,
    Layers,
    Link2,
    Loader2,
    RotateCcw,
    Search,
    Send,
    Sparkles,
    ThumbsUp,
    XCircle,
} from 'lucide-react'

const QUERY_WORD_LIMIT = 16

const SPANISH_STOP_WORDS = new Set([
    'a', 'al', 'algo', 'ante', 'como', 'con', 'contra', 'cual', 'cuando', 'de',
    'del', 'desde', 'donde', 'dos', 'el', 'ella', 'en', 'entre', 'era', 'es',
    'esa', 'ese', 'eso', 'esta', 'este', 'esto', 'hay', 'la', 'las', 'le', 'lo',
    'los', 'mas', 'me', 'mi', 'muy', 'no', 'o', 'para', 'pero', 'por', 'que',
    'se', 'segun', 'si', 'sin', 'sobre', 'son', 'su', 'sus', 'tambien', 'te',
    'tiene', 'un', 'una', 'unas', 'uno', 'unos', 'y',
])

function App() {
    const [step, setStep] = useState('query')
    const [query, setQuery] = useState('')
    const [expandedQuery, setExpandedQuery] = useState('')
    const [sessionId, setSessionId] = useState('')
    const [documents, setDocuments] = useState([])
    const [selectedDocIds, setSelectedDocIds] = useState(new Set())
    const [finalAnswer, setFinalAnswer] = useState('')
    const [finalDocs, setFinalDocs] = useState([])
    const [rocchioTerms, setRocchioTerms] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [showMinWordWarning, setShowMinWordWarning] = useState(false)
    const inputRef = useRef(null)

    useEffect(() => {
        if (step === 'query') {
            inputRef.current?.focus()
        }
    }, [step])

    function firstNonEmpty(...values) {
        for (const value of values) {
            if (value === undefined || value === null) continue
            const text = String(value).trim()
            if (text) return text
        }
        return ''
    }

    function getDocumentMetadata(doc) {
        return doc?.metadata || {}
    }

    function getDocumentId(doc, fallback = '') {
        const metadata = getDocumentMetadata(doc)
        return firstNonEmpty(
            doc?.id,
            doc?.chunk_id,
            metadata.chunk_id,
            doc?.doc_id,
            metadata.doc_id,
            doc?.document_key,
            metadata.document_key,
            doc?.url,
            metadata.url,
            fallback,
        )
    }

    function getDocumentTitle(doc) {
        const metadata = getDocumentMetadata(doc)
        if (doc?.title) return doc.title
        if (metadata.title) return metadata.title
        const url = getDocumentUrl(doc)
        if (url) return `Documento de ${getHostname(url)}`
        return 'Sin titulo'
    }

    function getDocumentContent(doc) {
        const metadata = getDocumentMetadata(doc)
        return firstNonEmpty(
            metadata.front_prev,
            doc?.content,
            doc?.text,
            doc?.page_content,
            doc?.content_preview,
        )
    }

    function getDocumentScore(doc) {
        const metadata = getDocumentMetadata(doc)
        const value = firstNonEmpty(doc?.score, metadata.score, metadata.final_score, 0)
        const score = Number(value)
        return Number.isFinite(score) ? score : 0
    }

    function getDocumentUrl(doc) {
        const metadata = getDocumentMetadata(doc)
        return firstNonEmpty(doc?.url, metadata.url)
    }

    function getDocumentSource(doc) {
        const metadata = getDocumentMetadata(doc)
        return firstNonEmpty(doc?.source, metadata.source, getHostname(getDocumentUrl(doc)), 'Local')
    }

    function getChunkIndex(doc) {
        const metadata = getDocumentMetadata(doc)
        const value = doc?.chunk_index ?? metadata.chunk_index
        return Number.isInteger(value) ? value : Number.isFinite(Number(value)) ? Number(value) : null
    }

    function getChunkTotal(doc) {
        const metadata = getDocumentMetadata(doc)
        const value = doc?.chunk_total ?? metadata.chunk_total
        return Number.isInteger(value) ? value : Number.isFinite(Number(value)) ? Number(value) : null
    }

    function getWordCount(content) {
        if (!content) return 0
        return content.trim().split(/\s+/).filter(Boolean).length
    }

    function getHostname(url) {
        if (!url) return ''
        try {
            return new URL(url).hostname.replace(/^www\./, '')
        } catch {
            return url
        }
    }

    function getDocumentKey(doc, fallback = '') {
        const explicitKey = firstNonEmpty(doc?.document_key, getDocumentMetadata(doc).document_key)
        if (explicitKey) return `key:${explicitKey}`

        const url = getDocumentUrl(doc)
        if (url) {
            try {
                const parsedUrl = new URL(url)
                parsedUrl.hash = ''
                return `url:${parsedUrl.toString()}`
            } catch {
                return `url:${url}`
            }
        }

        return `title:${getDocumentTitle(doc).toLowerCase()}-${fallback}`
    }

    function formatContent(content, maxLength = 300) {
        if (!content) return ''
        if (content.length <= maxLength) return content
        return `${content.substring(0, maxLength).trim()}...`
    }

    function formatScore(score) {
        if (!Number.isFinite(score) || score <= 0) return 'sin score'
        return score >= 1 ? score.toFixed(2) : score.toFixed(3)
    }

    function chunkLabel(chunk, position) {
        if (chunk.index !== null && chunk.total) {
            return `Fragmento ${chunk.index + 1}/${chunk.total}`
        }
        return `Fragmento ${position + 1}`
    }

    function groupDocuments(docs) {
        const groups = new Map()

        docs.forEach((doc, idx) => {
            const docId = getDocumentId(doc, `doc_${idx}`)
            const key = getDocumentKey(doc, docId)
            const content = getDocumentContent(doc)
            const score = getDocumentScore(doc)
            const chunk = {
                raw: doc,
                id: docId,
                content,
                score,
                wordCount: getWordCount(content),
                index: getChunkIndex(doc),
                total: getChunkTotal(doc),
            }

            if (!groups.has(key)) {
                groups.set(key, {
                    key,
                    ids: [],
                    chunks: [],
                    title: getDocumentTitle(doc),
                    url: getDocumentUrl(doc),
                    source: getDocumentSource(doc),
                    bestScore: score,
                    firstIndex: idx,
                    totalWords: 0,
                })
            }

            const group = groups.get(key)
            group.ids.push(docId)
            group.chunks.push(chunk)
            group.bestScore = Math.max(group.bestScore, score)
            group.totalWords += chunk.wordCount
            if (!group.url) group.url = getDocumentUrl(doc)
            if (!group.source) group.source = getDocumentSource(doc)
        })

        return Array.from(groups.values())
            .sort((a, b) => a.firstIndex - b.firstIndex)
            .map((group, idx) => {
                const uniqueIds = Array.from(new Set(group.ids))
                const bestChunk = [...group.chunks].sort((a, b) => b.score - a.score)[0] || group.chunks[0]
                return {
                    ...group,
                    ids: uniqueIds,
                    rank: idx + 1,
                    bestChunk,
                }
            })
    }

    function filterDocumentsByWordCount(docs) {
        return docs.filter(doc => getWordCount(getDocumentContent(doc)) >= 100)
    }

    const documentGroups = useMemo(() => groupDocuments(documents), [documents])
    const finalSourceGroups = useMemo(() => groupDocuments(finalDocs), [finalDocs])
    const queryWordCount = query.trim() ? query.trim().split(/\s+/).length : 0
    const isVerboseQuery = queryWordCount > QUERY_WORD_LIMIT
    const selectedDocumentCount = documentGroups.filter(group => group.ids.some(id => selectedDocIds.has(id))).length
    const selectedChunkCount = documentGroups.reduce(
        (total, group) => total + group.ids.filter(id => selectedDocIds.has(id)).length,
        0,
    )

    const compactVerboseQuery = () => {
        const rawTokens = query.trim().split(/\s+/).filter(Boolean)
        const meaningfulTokens = rawTokens
            .map(token => token.replace(/[¿?¡!,.;:()[\]{}"']/g, '').trim())
            .filter(Boolean)
            .filter(token => !SPANISH_STOP_WORDS.has(token.toLowerCase()))

        const compacted = (meaningfulTokens.length >= 4 ? meaningfulTokens : rawTokens)
            .slice(0, QUERY_WORD_LIMIT)
            .join(' ')

        setQuery(compacted)
    }

    const handleSearch = async () => {
        if (!query.trim()) return

        setLoading(true)
        setError('')
        setShowMinWordWarning(false)
        setRocchioTerms([])

        try {
            const res = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query.trim(),
                    top_k: 12,
                }),
            })

            if (!res.ok) throw new Error('Error en la API')

            const data = await res.json()
            const filteredDocs = filterDocumentsByWordCount(data.documents_retrieved || [])

            if (filteredDocs.length === 0) {
                setShowMinWordWarning(true)
            }

            setSessionId(data.session_id)
            setDocuments(filteredDocs)
            setSelectedDocIds(new Set())
            setStep('feedback')
            setExpandedQuery(data.expanded_query || '')
        } catch (err) {
            setError('No se pudieron obtener los documentos')
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const toggleDocumentGroup = (group) => {
        setSelectedDocIds(prev => {
            const next = new Set(prev)
            const allSelected = group.ids.every(id => next.has(id))

            group.ids.forEach(id => {
                if (allSelected) {
                    next.delete(id)
                } else {
                    next.add(id)
                }
            })

            return next
        })
    }

    const selectAll = () => {
        setSelectedDocIds(new Set(documentGroups.flatMap(group => group.ids)))
    }

    const clearSelection = () => {
        setSelectedDocIds(new Set())
    }

    const handleFeedback = async () => {
        setLoading(true)
        setError('')

        const relevant = Array.from(selectedDocIds)
        const nonRelevant = documents
            .map((doc, idx) => getDocumentId(doc, `doc_${idx}`))
            .filter(docId => !selectedDocIds.has(docId))

        try {
            const res = await fetch('/api/query/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    relevant_docs: relevant,
                    non_relevant_docs: nonRelevant,
                    original_query: query.trim(),
                    top_k: 6,
                }),
            })

            if (!res.ok) throw new Error('Error en la API')

            const data = await res.json()
            const terms = Object.entries(data.reformulated_query || {})
                .sort((a, b) => b[1] - a[1])
                .slice(0, 18)
                .map(([term, weight]) => ({ term, weight }))

            setFinalAnswer(data.answer)
            setFinalDocs(data.retrieved_docs || [])
            setRocchioTerms(terms)
            setStep('result')
        } catch (err) {
            setError('Error al aplicar feedback')
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const reset = () => {
        setStep('query')
        setQuery('')
        setExpandedQuery('')
        setSessionId('')
        setDocuments([])
        setSelectedDocIds(new Set())
        setFinalAnswer('')
        setFinalDocs([])
        setRocchioTerms([])
        setError('')
        setShowMinWordWarning(false)
        inputRef.current?.focus()
    }

    return (
        <div className="app-shell">
            <header className="app-header">
                <div className="brand">
                    <div className="brand-mark">
                        <Search size={22} />
                    </div>
                    <div>
                        <h1>SRI-RAG</h1>
                        <p>Recuperacion con feedback Rocchio</p>
                    </div>
                </div>

                <div className="step-tabs" aria-label="Estado del flujo">
                    <span className={step === 'query' ? 'active' : ''}>Consulta</span>
                    <span className={step === 'feedback' ? 'active' : ''}>Evidencia</span>
                    <span className={step === 'result' ? 'active' : ''}>Respuesta</span>
                </div>
            </header>

            {step === 'query' && (
                <main className="query-section">
                    <div className="query-toolbar">
                        <label htmlFor="query-input">Consulta</label>
                        <span className={isVerboseQuery ? 'word-count warning' : 'word-count'}>
                            {queryWordCount} palabras
                        </span>
                    </div>

                    <div className={isVerboseQuery ? 'search-panel warning' : 'search-panel'}>
                        <Search size={20} className="search-field-icon" />
                        <input
                            id="query-input"
                            ref={inputRef}
                            type="text"
                            placeholder="Ej. mejores portatiles ligeros con buena bateria"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                            className="search-input"
                        />
                        <button onClick={handleSearch} disabled={loading || !query.trim()} className="search-button">
                            {loading ? <Loader2 className="spinner" size={18} /> : <Send size={18} />}
                            <span>{loading ? 'Buscando' : 'Buscar'}</span>
                        </button>
                    </div>

                    {isVerboseQuery && (
                        <div className="inline-warning">
                            <FileText size={18} />
                            <span>Consulta larga: el modelo Dirichlet reparte peso entre todos los terminos y el ruido puede diluir la intencion.</span>
                            <button onClick={compactVerboseQuery} className="compact-button">
                                <Sparkles size={15} />
                                Reducir ruido
                            </button>
                        </div>
                    )}

                    {error && <div className="error-message">{error}</div>}
                </main>
            )}

            {step === 'feedback' && (
                <main className="feedback-section">
                    <div className="feedback-heading">
                        <div>
                            <p className="eyebrow">Rocchio</p>
                            <h2>Documentos recuperados</h2>
                        </div>

                    </div>

                    <div className="selection-bar">
                        <div className="selection-stats">
                            <span>{documentGroups.length} documentos</span>
                            <span>{documents.length} fragmentos</span>
                            <strong>{selectedDocumentCount} seleccionados</strong>
                            {selectedChunkCount > 0 && <span>{selectedChunkCount} fragmentos usados</span>}
                        </div>
                        <div className="selection-actions">
                            <button onClick={selectAll} className="action-btn">
                                <CheckCircle size={16} />
                                Todos
                            </button>
                            <button onClick={clearSelection} className="action-btn">
                                <XCircle size={16} />
                                Limpiar
                            </button>
                        </div>
                    </div>

                    {showMinWordWarning && (
                        <div className="inline-warning">
                            <FileText size={18} />
                            <span>No se encontraron documentos con suficiente contenido textual.</span>
                        </div>
                    )}

                    <div className="document-groups">
                        {documentGroups.map((group) => {
                            const isSelected = group.ids.some(id => selectedDocIds.has(id))
                            const visibleChunks = group.chunks.slice(0, 4)
                            const remainingChunks = group.chunks.length - visibleChunks.length

                            return (
                                <article key={group.key} className={isSelected ? 'doc-group selected' : 'doc-group'}>
                                    <div className="doc-group-top">
                                        <div className="doc-rank">#{group.rank}</div>
                                        <div className="doc-main">
                                            <h3>{group.title}</h3>
                                            <div className="doc-facts">
                                                <span><Layers size={14} /> {group.chunks.length} {group.chunks.length === 1 ? 'fragmento' : 'fragmentos'}</span>
                                                <span>score {formatScore(group.bestScore)}</span>
                                                {group.url && (
                                                    <a
                                                        href={group.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        onClick={(event) => event.stopPropagation()}
                                                    >
                                                        <Globe size={14} />
                                                        {getHostname(group.url)}
                                                    </a>
                                                )}
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => toggleDocumentGroup(group)}
                                            className={isSelected ? 'select-doc-button active' : 'select-doc-button'}
                                            aria-pressed={isSelected}
                                        >
                                            {isSelected ? <CheckCircle size={16} /> : <ThumbsUp size={16} />}
                                            {isSelected ? 'Seleccionado' : 'Relevante'}
                                        </button>
                                    </div>

                                    <p className="doc-excerpt">
                                        {formatContent(group.bestChunk?.content, 290)}
                                    </p>

                                    {group.chunks.length > 1 && (
                                        <div className="chunk-strip" aria-label="Fragmentos agrupados">
                                            {visibleChunks.map((chunk, idx) => (
                                                <span key={`${chunk.id}-${idx}`}>{chunkLabel(chunk, idx)}</span>
                                            ))}
                                            {remainingChunks > 0 && <span>+{remainingChunks}</span>}
                                        </div>
                                    )}
                                </article>
                            )
                        })}
                    </div>

                    {documentGroups.length === 0 && (
                        <div className="empty-state">
                            <FileText size={44} strokeWidth={1.5} />
                            <p>No se encontraron documentos con suficiente contenido.</p>
                            <button onClick={reset} className="action-btn">
                                <RotateCcw size={16} />
                                Intentar de nuevo
                            </button>
                        </div>
                    )}

                    <div className="feedback-footer">
                        <button onClick={reset} className="secondary-btn">
                            <RotateCcw size={16} />
                            Nueva consulta
                        </button>
                        <button
                            onClick={handleFeedback}
                            disabled={loading}
                            className="primary-btn"
                        >
                            {loading ? <Loader2 className="spinner" size={16} /> : <Brain size={16} />}
                            {loading ? 'Procesando' : 'Aplicar Rocchio'}
                            <ChevronRight size={16} />
                        </button>
                    </div>

                    {error && <div className="error-message">{error}</div>}
                </main>
            )}

            {step === 'result' && (
                <main className="result-section">
                    <div className="result-header">
                        <button onClick={reset} className="secondary-btn">
                            <RotateCcw size={16} />
                            Nueva consulta
                        </button>
                    </div>

                    <div className="result-layout">
                        <article className="answer-panel">
                            <div className="section-title">
                                <Sparkles size={20} />
                                <h2>Respuesta final</h2>
                            </div>
                            <div className="answer-content">{finalAnswer}</div>
                        </article>

                        {// rocchioTerms.length > 0 && (
                            //   <aside className="rocchio-panel">
                            //     <div className="section-title">
                            //       <Brain size={19} />
                            //     <h2>Rocchio</h2>
                            //   </div>
                            //   <div className="term-cloud">
                            //       {rocchioTerms.map(({ term, weight }) => (
                            //           <span
                            //                key={term}
                            //                style={{ '--term-weight': Math.min(1, Math.max(0.35, weight * 8)) }}
                            //           >
                            //</div>                {term}
                            //             </span>
                            //         ))}
                            //       </div>
                            //    </aside>
                            //   )
                        }
                    </div>

                    <section className="sources-section">
                        <div className="sources-heading">
                            <div className="section-title">
                                <Link2 size={19} />
                                <h2>Documentos usados</h2>
                            </div>
                            <span>{finalSourceGroups.length} documentos, {finalDocs.length} fragmentos</span>
                        </div>

                        <div className="source-grid">
                            {finalSourceGroups.map((group) => (
                                <article key={group.key} className="source-card">
                                    <div className="source-card-top">
                                        <span className="source-number">{group.rank}</span>
                                        <h3>{group.title}</h3>
                                    </div>
                                    <p>{formatContent(group.bestChunk?.content, 180)}</p>
                                    <div className="source-meta">
                                        <span><Layers size={14} /> {group.chunks.length} {group.chunks.length === 1 ? 'fragmento' : 'fragmentos'}</span>
                                        <span>score {formatScore(group.bestScore)}</span>
                                    </div>
                                    {group.url && (
                                        <a href={group.url} target="_blank" rel="noopener noreferrer" className="source-link">
                                            <ExternalLink size={14} />
                                            {getHostname(group.url)}
                                        </a>
                                    )}
                                </article>
                            ))}
                        </div>
                    </section>
                </main>
            )}

            <style>{`
                body {
                    margin: 0;
                    background: #f4f6f1;
                    color: #162022;
                }

                .app-shell {
                    min-height: 100vh;
                    padding: 28px 24px 48px;
                    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    background:
                        linear-gradient(180deg, rgba(255,255,255,0.72), rgba(244,246,241,0.96)),
                        #f4f6f1;
                }

                .app-header {
                    max-width: 1180px;
                    margin: 0 auto 28px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 18px;
                }

                .brand {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }

                .brand-mark {
                    width: 44px;
                    height: 44px;
                    border-radius: 8px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    color: #ffffff;
                    background: #0f766e;
                    box-shadow: 0 8px 18px rgba(15, 118, 110, 0.22);
                }

                .brand h1,
                .brand p,
                .section-title h2,
                .feedback-heading h2,
                .doc-main h3,
                .source-card h3 {
                    margin: 0;
                }

                .brand h1 {
                    font-size: 1.35rem;
                    line-height: 1.1;
                }

                .brand p {
                    margin-top: 3px;
                    color: #64706a;
                    font-size: 0.88rem;
                }

                .step-tabs {
                    display: flex;
                    gap: 6px;
                    padding: 4px;
                    border: 1px solid #d8ddd4;
                    border-radius: 8px;
                    background: #ffffff;
                }

                .step-tabs span {
                    min-width: 86px;
                    text-align: center;
                    padding: 8px 10px;
                    border-radius: 6px;
                    color: #5f6b65;
                    font-size: 0.86rem;
                    font-weight: 650;
                }

                .step-tabs span.active {
                    color: #ffffff;
                    background: #162022;
                }

                .query-section,
                .feedback-section,
                .result-section {
                    max-width: 1180px;
                    margin: 0 auto;
                }

                .query-section {
                    padding-top: 92px;
                    max-width: 840px;
                }

                .query-toolbar {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }

                .query-toolbar label {
                    font-weight: 700;
                    color: #243033;
                }

                .word-count {
                    color: #64706a;
                    font-size: 0.86rem;
                }

                .word-count.warning {
                    color: #a15c06;
                    font-weight: 700;
                }

                .search-panel {
                    display: grid;
                    grid-template-columns: auto minmax(0, 1fr) auto;
                    align-items: center;
                    gap: 10px;
                    padding: 10px;
                    border: 1px solid #d8ddd4;
                    border-radius: 8px;
                    background: #ffffff;
                    box-shadow: 0 18px 38px rgba(22, 32, 34, 0.08);
                }

                .search-panel.warning {
                    border-color: #d68a22;
                }

                .search-field-icon {
                    margin-left: 8px;
                    color: #0f766e;
                }

                .search-input {
                    min-width: 0;
                    border: 0;
                    outline: 0;
                    color: #162022;
                    background: transparent;
                    font-size: 1.03rem;
                    line-height: 1.4;
                }

                .search-input::placeholder {
                    color: #8b948f;
                }

                button {
                    font: inherit;
                }

                .search-button,
                .primary-btn,
                .secondary-btn,
                .action-btn,
                .select-doc-button,
                .compact-button {
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    min-height: 38px;
                    border-radius: 8px;
                    border: 1px solid transparent;
                    cursor: pointer;
                    font-size: 0.9rem;
                    font-weight: 750;
                    transition: background-color 0.16s, border-color 0.16s, transform 0.16s, box-shadow 0.16s;
                    white-space: nowrap;
                }

                .search-button,
                .primary-btn {
                    padding: 0 16px;
                    color: #ffffff;
                    background: #0f766e;
                    box-shadow: 0 8px 18px rgba(15, 118, 110, 0.2);
                }

                .search-button:hover:not(:disabled),
                .primary-btn:hover:not(:disabled) {
                    background: #115e59;
                    transform: translateY(-1px);
                }

                .secondary-btn,
                .action-btn,
                .compact-button {
                    padding: 0 13px;
                    color: #243033;
                    background: #ffffff;
                    border-color: #d8ddd4;
                }

                .secondary-btn:hover,
                .action-btn:hover,
                .compact-button:hover {
                    background: #eef2ed;
                }

                button:disabled {
                    cursor: not-allowed;
                    opacity: 0.55;
                    transform: none;
                    box-shadow: none;
                }

                .inline-warning,
                .error-message {
                    margin-top: 14px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    padding: 12px 14px;
                    border-radius: 8px;
                    font-size: 0.92rem;
                    line-height: 1.45;
                }

                .inline-warning {
                    border: 1px solid #f0c47c;
                    color: #704309;
                    background: #fff7df;
                }

                .inline-warning span {
                    flex: 1;
                }

                .error-message {
                    border: 1px solid #f0b5b5;
                    color: #8f1d1d;
                    background: #fff0f0;
                }

                .feedback-heading,
                .selection-bar,
                .result-header,
                .sources-heading {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 16px;
                }

                .feedback-heading {
                    margin-bottom: 16px;
                }

                .eyebrow {
                    margin: 0 0 4px;
                    color: #0f766e;
                    font-size: 0.76rem;
                    font-weight: 800;
                    text-transform: uppercase;
                }

                .feedback-heading h2 {
                    font-size: 1.55rem;
                }

                .query-snapshot {
                    max-width: 430px;
                    padding: 10px 12px;
                    border: 1px solid #d8ddd4;
                    border-radius: 8px;
                    background: #ffffff;
                }

                .query-snapshot span,
                .sources-heading > span {
                    color: #64706a;
                    font-size: 0.78rem;
                    font-weight: 750;
                }

                .query-snapshot p {
                    margin: 4px 0 0;
                    color: #243033;
                    font-size: 0.9rem;
                    line-height: 1.35;
                }

                .selection-bar {
                    position: sticky;
                    top: 12px;
                    z-index: 2;
                    padding: 12px;
                    border: 1px solid #d8ddd4;
                    border-radius: 8px;
                    background: rgba(255, 255, 255, 0.94);
                    backdrop-filter: blur(8px);
                }

                .selection-stats,
                .selection-actions,
                .doc-facts,
                .source-meta {
                    display: flex;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 9px;
                }

                .selection-stats span,
                .selection-stats strong,
                .doc-facts span,
                .source-meta span {
                    display: inline-flex;
                    align-items: center;
                    gap: 5px;
                    min-height: 26px;
                    padding: 0 9px;
                    border-radius: 6px;
                    color: #42504a;
                    background: #eef2ed;
                    font-size: 0.82rem;
                    font-weight: 650;
                }

                .selection-stats strong {
                    color: #ffffff;
                    background: #0f766e;
                }

                .document-groups {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 14px;
                    margin-top: 16px;
                }

                .doc-group,
                .answer-panel,
                .rocchio-panel,
                .source-card,
                .empty-state {
                    border: 1px solid #d8ddd4;
                    border-radius: 8px;
                    background: #ffffff;
                    box-shadow: 0 10px 24px rgba(22, 32, 34, 0.05);
                }

                .doc-group {
                    padding: 16px;
                    transition: border-color 0.16s, box-shadow 0.16s, transform 0.16s;
                }

                .doc-group:hover {
                    border-color: #9bbab3;
                    box-shadow: 0 14px 28px rgba(22, 32, 34, 0.08);
                    transform: translateY(-1px);
                }

                .doc-group.selected {
                    border-color: #0f766e;
                    box-shadow: 0 14px 28px rgba(15, 118, 110, 0.13);
                }

                .doc-group-top {
                    display: grid;
                    grid-template-columns: auto minmax(0, 1fr) auto;
                    align-items: start;
                    gap: 12px;
                }

                .doc-rank {
                    min-width: 34px;
                    color: #0f766e;
                    font-weight: 850;
                }

                .doc-main {
                    min-width: 0;
                }

                .doc-main h3,
                .source-card h3 {
                    color: #162022;
                    font-size: 0.98rem;
                    line-height: 1.3;
                }

                .doc-facts {
                    margin-top: 9px;
                }

                .doc-facts a,
                .source-link {
                    display: inline-flex;
                    align-items: center;
                    gap: 5px;
                    color: #0f766e;
                    font-size: 0.82rem;
                    font-weight: 700;
                    text-decoration: none;
                }

                .doc-facts a:hover,
                .source-link:hover {
                    text-decoration: underline;
                }

                .select-doc-button {
                    padding: 0 12px;
                    color: #5b3b08;
                    background: #fff6dc;
                    border-color: #edc46e;
                }

                .select-doc-button.active {
                    color: #ffffff;
                    background: #0f766e;
                    border-color: #0f766e;
                }

                .doc-excerpt,
                .source-card p,
                .answer-content {
                    color: #42504a;
                    line-height: 1.56;
                }

                .doc-excerpt {
                    margin: 13px 0 0;
                    font-size: 0.92rem;
                }

                .chunk-strip {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 7px;
                    margin-top: 13px;
                }

                .chunk-strip span,
                .term-cloud span {
                    display: inline-flex;
                    align-items: center;
                    min-height: 26px;
                    padding: 0 9px;
                    border-radius: 6px;
                    font-size: 0.8rem;
                    font-weight: 720;
                }

                .chunk-strip span {
                    color: #36514f;
                    background: #e4f1ed;
                }

                .empty-state {
                    display: grid;
                    place-items: center;
                    gap: 12px;
                    min-height: 240px;
                    margin-top: 18px;
                    color: #64706a;
                    text-align: center;
                }

                .empty-state p {
                    margin: 0;
                }

                .feedback-footer {
                    position: sticky;
                    bottom: 12px;
                    display: flex;
                    justify-content: space-between;
                    gap: 14px;
                    margin-top: 18px;
                    padding: 12px;
                    border: 1px solid #d8ddd4;
                    border-radius: 8px;
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(8px);
                }

                .result-header {
                    justify-content: flex-end;
                    margin-bottom: 16px;
                }

                .result-layout {
                    display: grid;
                    grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.55fr);
                    gap: 16px;
                    align-items: start;
                }

                .answer-panel,
                .rocchio-panel,
                .source-card {
                    padding: 18px;
                }

                .section-title {
                    display: flex;
                    align-items: center;
                    gap: 9px;
                    color: #162022;
                }

                .section-title h2 {
                    font-size: 1.08rem;
                }

                .answer-content {
                    margin-top: 16px;
                    white-space: pre-wrap;
                    font-size: 1rem;
                }

                .term-cloud {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    margin-top: 16px;
                }

                .term-cloud span {
                    color: #ffffff;
                    background: rgba(15, 118, 110, var(--term-weight));
                }

                .sources-section {
                    margin-top: 18px;
                }

                .sources-heading {
                    margin-bottom: 12px;
                }

                .source-grid {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 14px;
                }

                .source-card-top {
                    display: grid;
                    grid-template-columns: auto minmax(0, 1fr);
                    gap: 10px;
                    align-items: start;
                }

                .source-number {
                    width: 28px;
                    height: 28px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 6px;
                    color: #ffffff;
                    background: #162022;
                    font-weight: 850;
                    font-size: 0.82rem;
                }

                .source-card p {
                    margin: 12px 0;
                    font-size: 0.9rem;
                }

                .source-meta {
                    margin-bottom: 12px;
                }

                .spinner {
                    animation: spin 1s linear infinite;
                }

                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }

                @media (max-width: 980px) {
                    .document-groups,
                    .result-layout,
                    .source-grid {
                        grid-template-columns: 1fr;
                    }

                    .query-section {
                        padding-top: 48px;
                    }
                }

                @media (max-width: 720px) {
                    .app-shell {
                        padding: 18px 14px 36px;
                    }

                    .app-header,
                    .feedback-heading,
                    .selection-bar,
                    .sources-heading {
                        align-items: stretch;
                        flex-direction: column;
                    }

                    .step-tabs {
                        width: 100%;
                    }

                    .step-tabs span {
                        min-width: 0;
                        flex: 1;
                    }

                    .search-panel {
                        grid-template-columns: auto minmax(0, 1fr);
                    }

                    .search-button {
                        grid-column: 1 / -1;
                        width: 100%;
                    }

                    .doc-group-top {
                        grid-template-columns: auto minmax(0, 1fr);
                    }

                    .select-doc-button {
                        grid-column: 1 / -1;
                        width: 100%;
                    }

                    .feedback-footer {
                        flex-direction: column;
                    }

                    .feedback-footer button {
                        width: 100%;
                    }
                }
            `}</style>
        </div>
    )
}

export default App
