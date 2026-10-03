import { useState } from "react"
import { deleteDocument, DuplicateError, uploadDocuments, type Document } from "@/api/client"
import { DocumentList } from "@/components/DocumentList"
import { DuplicateDialog } from "@/components/DuplicateDialog"
import { Dropzone } from "@/components/Dropzone"
import { useDocuments } from "@/hooks/useDocuments"

export function UploadPage() {
  const { documents, error, refresh } = useDocuments()
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // Files the api reported as already uploaded, waiting for the user's answer.
  const [duplicates, setDuplicates] = useState<File[]>([])
  const [overwriteError, setOverwriteError] = useState<string | null>(null)

  async function upload(files: File[]) {
    try {
      await uploadDocuments(files)
    } catch (e) {
      if (!(e instanceof DuplicateError)) throw e
      setDuplicates(files)
    } finally {
      // Refresh even when the request fails, so the list always matches the server.
      await refresh()
    }
  }

  async function overwrite() {
    const files = duplicates
    setDuplicates([])
    try {
      await uploadDocuments(files, true)
      setOverwriteError(null)
    } catch (e) {
      setOverwriteError((e as Error).message)
    }
    await refresh()
  }

  async function remove(document: Document) {
    try {
      await deleteDocument(document.id)
      setDeleteError(null)
    } catch (e) {
      setDeleteError((e as Error).message)
    }
    await refresh()
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl">Upload</h1>
      <Dropzone onUpload={upload} />
      {overwriteError && <p className="text-sm text-destructive">{overwriteError}</p>}
      <DuplicateDialog files={duplicates} onOverwrite={overwrite} onCancel={() => setDuplicates([])} />
      <section className="space-y-3">
        <h2 className="text-lg">Documents</h2>
        {error && <p className="text-sm text-destructive">Could not load documents: {error}</p>}
        {deleteError && <p className="text-sm text-destructive">{deleteError}</p>}
        {documents && <DocumentList documents={documents} onDelete={remove} />}
      </section>
    </div>
  )
}
