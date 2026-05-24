import { useState, useEffect, useRef } from 'react'
import { BookOpen, ExternalLink, Loader2, Send, Search, CheckCircle, ThumbsUp, RotateCcw } from 'lucide-react'

function App() {
    const [step, setStep] = useState('query')
    const [query, setQuery] = useState('')
    const [expanded_query, setExpanded_query] = useState('')
    const [sessionId, setSessionId] = useState('')
    const [documents, setDocuments] = useState([])
    const [selectedDocIds, setSelectedDocIds] = useState(new Set())
    const [finalAnswer, setFinalAnswer] = useState('')
    const [finalDocs, setFinalDocs] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const inputRef = useRef(null)

    useEffect(() => {
        inputRef.current?.focus()
    }, [step])

    const handleSearch = async () => {
        if (!query.trim()) return

        setLoading(true)
        setError('')

        try {
            const res = await fetch(`/api/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    top_k: 10,

                }),
            })

            if (!res.ok) throw new Error('Error en la API')

            const data = await res.json()
            setSessionId(data.session_id)
            setDocuments(data.documents_retrieved)
            setSelectedDocIds(new Set())
            setStep('feedback')
            setExpanded_query(data.expanded_query)

        } catch (err) {
            setError('No se pudieron obtener los documentos')
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const toggleDocument = (id) => {
        setSelectedDocIds(prev => {
            const newSet = new Set(prev)
            if (newSet.has(id)) {
                newSet.delete(id)
            } else {
                newSet.add(id)
            }
            return newSet
        })
    }

    const selectAll = () => {
        const allIds = new Set(documents.map(doc => doc.id || doc.doc_id || doc.metadata?.url))
        setSelectedDocIds(allIds)
    }

    const clearSelection = () => {
        setSelectedDocIds(new Set())
    }

    const handleFeedback = async () => {
        setLoading(true)

        const relevant = Array.from(selectedDocIds)
        const nonRelevant = documents
            .filter(doc => {
                const docId = doc.id || doc.doc_id || doc.metadata?.url
                return !selectedDocIds.has(docId)
            })
            .map(doc => doc.id || doc.doc_id || doc.metadata?.url)

        try {
            const res = await fetch(`api/query/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    relevant_docs: relevant,
                    non_relevant_docs: nonRelevant,
                    original_query: query,
                    top_k: 3
                }),
            })

            if (!res.ok) throw new Error('Error en la API')

            const data = await res.json()
            setFinalAnswer(data.answer)
            setFinalDocs(data.retrieved_docs)
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
        setSessionId('')
        setDocuments([])
        setSelectedDocIds(new Set())
        setFinalAnswer('')
        setFinalDocs([])
        setError('')
        inputRef.current?.focus()
    }

    // Función mejorada para extraer el título del documento
    const getDocumentTitle = (doc) => {
        if (doc.title) return doc.title
        if (doc.metadata?.title) return doc.metadata.title
        if (doc.metadata?.url) {
            const hostname = getHostname(doc.metadata.url)
            return `Documento de ${hostname}`
        }
        return "Sin título"
    }

    // Función mejorada para extraer el contenido del documento
    const getDocumentContent = (doc) => {
        if (doc.content) return doc.content
        if (doc.page_content) return doc.page_content
        if (doc.text) return doc.text
        if (doc.content_preview) return doc.content_preview
        return ""
    }

    // Función mejorada para extraer el score del documento
    const getDocumentScore = (doc) => {
        if (doc.score) return doc.score
        if (doc.metadata?.score) return doc.metadata.score
        if (doc.metadata?.final_score) return doc.metadata.final_score
        return 0
    }

    // Función mejorada para extraer la URL del documento
    const getDocumentUrl = (doc) => {
        if (doc.url) return doc.url
        if (doc.metadata?.url) return doc.metadata.url
        return null
    }

    const formatContent = (content, maxLength = 300) => {
        if (!content) return ''
        if (content.length <= maxLength) return content
        return content.substring(0, maxLength) + '...'
    }

    const getHostname = (url) => {
        if (!url) return ''
        try {
            return new URL(url).hostname
        } catch {
            return url
        }
    }

    return (
        <div className="container">
            <h1 className="title">
                🔁 RAG con retroalimentación (Rocchio)
            </h1>

            {step === 'query' && (
                <>
                    <div className="search-bar">
                        <input
                            ref={inputRef}
                            type="text"
                            placeholder="Escribe tu consulta aquí..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                        />
                        <button onClick={handleSearch} disabled={loading}>
                            {loading ? <Loader2 className="spinner" /> : <Send />}
                        </button>
                    </div>

                    {error && <div className="error">{error}</div>}

                    <div className="info-text">
                        <p>🔍 Escribe una pregunta y el sistema recuperará documentos relevantes.</p>
                        <p>Luego podrás seleccionar cuáles son realmente útiles para afinar la búsqueda.</p>
                    </div>
                </>
            )}

            {step === 'feedback' && (
                <>
                    <div className="feedback-header">
                        <div className="session-info">
                            <span className="badge">Sesión: {sessionId}</span>
                            {expanded_query && expanded_query !== query && (
                                <div className="expanded-query">
                                    <strong>🔍 Query expandida:</strong> {expanded_query}
                                </div>
                            )}
                        </div>

                        <div className="feedback-actions">
                            <button onClick={selectAll} className="btn-secondary">
                                <CheckCircle size={16} /> Seleccionar todos
                            </button>
                            <button onClick={clearSelection} className="btn-secondary">
                                Limpiar selección
                            </button>
                        </div>

                        <p className="feedback-instruction">
                            📖 Selecciona los documentos <strong>relevantes</strong> para tu consulta.
                            <br />
                            <small>(Los no seleccionados se considerarán no relevantes)</small>
                        </p>
                    </div>

                    <div className="documents-list">
                        {documents.map((doc, idx) => {
                            const docId = doc.id || doc.doc_id || doc.metadata?.url || `doc_${idx}`
                            const title = getDocumentTitle(doc)
                            const content = getDocumentContent(doc)
                            const score = getDocumentScore(doc)
                            const url = getDocumentUrl(doc)

                            return (
                                <div
                                    key={docId}
                                    className={`document-card ${selectedDocIds.has(docId) ? 'selected' : ''}`}
                                    onClick={() => toggleDocument(docId)}
                                >
                                    <div className="doc-header">
                                        <div className="doc-rank">#{idx + 1}</div>
                                        <div className="doc-title">
                                            <strong>{title}</strong>
                                        </div>
                                        <div className="doc-checkbox">
                                            <input
                                                type="checkbox"
                                                checked={selectedDocIds.has(docId)}
                                                onChange={() => toggleDocument(docId)}
                                                onClick={(e) => e.stopPropagation()}
                                            />
                                        </div>
                                    </div>

                                    <div className="doc-content">
                                        <div className="doc-text">
                                            {formatContent(content, 250)}
                                        </div>

                                        {score > 0 && (
                                            <div className="doc-score">
                                                📊 Relevancia: {(score * 100).toFixed(1)}%
                                            </div>
                                        )}

                                        {url && (
                                            <a
                                                href={url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="doc-link"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                <ExternalLink size={14} />
                                                {getHostname(url)}
                                            </a>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>

                    {documents.length === 0 && (
                        <div className="info-text">
                            <p>No se encontraron documentos. Intenta con otra consulta.</p>
                        </div>
                    )}

                    <div className="feedback-footer">
                        <button onClick={reset} className="btn-secondary">
                            <RotateCcw size={16} /> Reiniciar
                        </button>
                        <button onClick={handleFeedback} disabled={loading || documents.length === 0} className="btn-primary">
                            {loading ? <Loader2 className="spinner" /> : <ThumbsUp size={16} />}
                            {loading ? 'Procesando...' : 'Generar respuesta final'}
                        </button>
                    </div>

                    {error && <div className="error">{error}</div>}
                </>
            )}

            {step === 'result' && (
                <>
                    <div className="result-header">
                        <button onClick={reset} className="btn-secondary">
                            <RotateCcw size={16} /> Nueva consulta
                        </button>
                    </div>

                    <div className="final-answer">
                        <h2>📝 Respuesta final</h2>
                        <div className="answer-text">{finalAnswer}</div>
                    </div>

                    <div className="retrieved-docs">
                        <h3>📚 Documentos utilizados ({finalDocs.length})</h3>
                        {finalDocs.map((doc, idx) => (
                            <div key={doc.id || idx} className="doc-source">
                                <div className="source-rank">{idx + 1}.</div>
                                <div className="source-content">
                                    <div className="source-title">
                                        <strong>{doc.title || doc.metadata?.title || "Sin título"}</strong>
                                    </div>
                                    <div className="source-text">
                                        {formatContent(doc.text || doc.content || doc.page_content, 200)}
                                    </div>
                                    {doc.url && (
                                        <a href={doc.url} target="_blank" rel="noopener noreferrer">
                                            <ExternalLink size={14} /> {getHostname(doc.url)}
                                        </a>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    {error && <div className="error">{error}</div>}
                </>
            )}

            <style jsx>{`
        .container {
          max-width: 900px;
          margin: 0 auto;
          padding: 20px;
          font-family: system-ui, -apple-system, sans-serif;
        }
        
        .title {
          text-align: center;
          margin-bottom: 30px;
          color: #333;
        }
        
        .search-bar {
          display: flex;
          gap: 10px;
          margin-bottom: 20px;
        }
        
        .search-bar input {
          flex: 1;
          padding: 12px 16px;
          font-size: 16px;
          border: 1px solid #ddd;
          border-radius: 8px;
          outline: none;
        }
        
        .search-bar input:focus {
          border-color: #4CAF50;
        }
        
        .search-bar button {
          padding: 12px 24px;
          background: #4CAF50;
          color: white;
          border: none;
          border-radius: 8px;
          cursor: pointer;
        }
        
        .search-bar button:disabled {
          background: #ccc;
          cursor: not-allowed;
        }
        
        .info-text {
          background: #e3f2fd;
          padding: 15px;
          border-radius: 8px;
          margin-top: 20px;
        }
        
        .info-text p {
          margin: 5px 0;
          color: #1565c0;
        }
        
        .expanded-query {
          background: #fff3e0;
          padding: 8px;
          border-radius: 4px;
          margin-top: 8px;
          font-size: 14px;
        }
        
        .error {
          background: #ffebee;
          color: #c62828;
          padding: 12px;
          border-radius: 8px;
          margin: 10px 0;
        }
        
        .feedback-header {
          margin-bottom: 20px;
        }
        
        .session-info {
          margin-bottom: 15px;
        }
        
        .badge {
          background: #e0e0e0;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-family: monospace;
        }
        
        .feedback-actions {
          display: flex;
          gap: 10px;
          margin-bottom: 15px;
        }
        
        .feedback-instruction {
          background: #fff3e0;
          padding: 10px;
          border-radius: 8px;
          margin: 10px 0;
        }
        
        .documents-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin: 20px 0;
          max-height: 500px;
          overflow-y: auto;
        }
        
        .document-card {
          border: 1px solid #ddd;
          border-radius: 8px;
          padding: 12px;
          cursor: pointer;
          transition: all 0.2s;
        }
        
        .document-card:hover {
          background: #f5f5f5;
        }
        
        .document-card.selected {
          background: #e8f5e9;
          border-color: #4CAF50;
        }
        
        .doc-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          gap: 10px;
        }
        
        .doc-rank {
          font-weight: bold;
          color: #666;
          min-width: 35px;
        }
        
        .doc-title {
          flex: 1;
          font-size: 14px;
        }
        
        .doc-title strong {
          color: #2c3e50;
        }
        
        .doc-content {
          margin-left: 35px;
        }
        
        .doc-text {
          margin-bottom: 8px;
          line-height: 1.5;
          color: #555;
          font-size: 13px;
        }
        
        .doc-score {
          font-size: 12px;
          color: #4CAF50;
          margin: 5px 0;
        }
        
        .doc-link {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          color: #1976d2;
          text-decoration: none;
        }
        
        .doc-link:hover {
          text-decoration: underline;
        }
        
        .feedback-footer {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          margin-top: 20px;
        }
        
        .btn-primary, .btn-secondary {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 20px;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
        }
        
        .btn-primary {
          background: #4CAF50;
          color: white;
        }
        
        .btn-primary:disabled {
          background: #ccc;
          cursor: not-allowed;
        }
        
        .btn-secondary {
          background: #f0f0f0;
          color: #333;
        }
        
        .btn-secondary:hover {
          background: #e0e0e0;
        }
        
        .result-header {
          display: flex;
          justify-content: flex-end;
          margin-bottom: 20px;
        }
        
        .final-answer {
          background: #e8f5e9;
          padding: 20px;
          border-radius: 8px;
          margin: 20px 0;
        }
        
        .answer-text {
          font-size: 18px;
          line-height: 1.6;
        }
        
        .retrieved-docs {
          margin-top: 30px;
        }
        
        .retrieved-docs h3 {
          margin-bottom: 15px;
        }
        
        .doc-source {
          display: flex;
          gap: 10px;
          padding: 12px;
          border-bottom: 1px solid #eee;
        }
        
        .source-rank {
          font-weight: bold;
          color: #666;
        }
        
        .source-content {
          flex: 1;
        }
        
        .source-title {
          margin-bottom: 5px;
          font-weight: bold;
          color: #2c3e50;
        }
        
        .source-text {
          margin-bottom: 8px;
          color: #555;
          font-size: 13px;
        }
        
        .source-content a {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 12px;
          color: #1976d2;
          text-decoration: none;
        }
        
        .spinner {
          animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
        </div>
    )
}

export default App