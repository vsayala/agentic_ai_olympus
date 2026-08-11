# Vendor Register

| Vendor or component | Purpose | Data boundary | Approval state |
|---|---|---|---|
| GitHub Copilot SDK | Model sessions and orchestration | Prompts and supplied evidence | Existing project dependency; production use requires organizational approval |
| FastEmbed / BAAI model | Local embeddings | Local document chunks | Existing locked dependency |
| Milvus Lite | Local vector persistence | Local embeddings and source metadata | Existing locked dependency |
| Streamlit | Local application UI | Session state and displayed results | Existing locked dependency |
| Azure Databricks | Optional governed cloud retrieval | Configured source and platform data | Deployment approval required |

Contracts, security assessments, subprocessors, data-processing terms, and renewal evidence remain
in the approved procurement system and must be referenced through the external evidence index when
applicable.