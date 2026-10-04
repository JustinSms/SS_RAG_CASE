import { useState } from "react"
import { deleteDocument, DuplicateError, uploadDocument, type Document } from "@/api/client"
import { DocumentList } from "@/components/DocumentList"
import { DuplicateDialog } from "@/components/DuplicateDialog"
import { Dropzone } from "@/components/Dropzone"
import { PageHeader } from "@/components/PageHeader"
import { useDocuments } from "@/hooks/useDocuments"

export function UploadPage() {
  const { documents, error, refresh } = useDocuments()
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // Files the api reported as already uploaded, waiting for the user's answer.
  const [duplicates, setDuplicates] = useState<File[]>([])
  const [overwriteError, setOverwriteError] = useState<string | null>(null)

  // Uploads the files one by one. Duplicates wait for the dialog; other refusals come back as messages.
  async function upload(files: File[]): Promise<string[]> {
    const found: File[] = []
    const messages: string[] = []
    for (const file of files) {
      try {
        await uploadDocument(file)
      } catch (e) {
        if (e instanceof DuplicateError) found.push(file)
        else messages.push((e as Error).message)
      }
    }
    setDuplicates(found)
    // Refresh even when a request fails, so the list always matches the server.
    await refresh()
    return messages
  }

  async function overwrite() {
    const files = duplicates
    setDuplicates([])
    const messages: string[] = []
    for (const file of files) {
      try {
        await uploadDocument(file, true)
      } catch (e) {
        messages.push((e as Error).message)
      }
    }
    setOverwriteError(messages.length > 0 ? messages.join(" ") : null)
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

  const ready = documents?.filter((d) => d.status === "ready").length ?? 0

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-8 px-8 py-10">
        <PageHeader title="Upload" description="Add PDFs. Each one is parsed, split into sections and indexed for chat." />
        <Dropzone onUpload={upload} />
        {overwriteError && <p className="text-sm text-destructive">{overwriteError}</p>}
        <DuplicateDialog files={duplicates} onOverwrite={overwrite} onCancel={() => setDuplicates([])} />
        <section className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg">Documents</h2>
            {documents && documents.length > 0 && (
              <span className="text-sm text-muted-foreground">
                {ready} of {documents.length} ready
              </span>
            )}
          </div>
          {error && <p className="text-sm text-destructive">Could not load documents: {error}</p>}
          {deleteError && <p className="text-sm text-destructive">{deleteError}</p>}
          {documents && <DocumentList documents={documents} onDelete={remove} />}
        </section>
      </div>
    </div>
  )
}
