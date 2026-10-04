import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

type Props = { files: File[]; onOverwrite: () => void; onCancel: () => void }

// Shown when the api answers 409. The files stay with the page until the user decides.
export function DuplicateDialog({ files, onOverwrite, onCancel }: Props) {
  return (
    <Dialog open={files.length > 0} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Already uploaded</DialogTitle>
          <DialogDescription>
            {files.length > 1
              ? "These documents are already uploaded. Overwrite them?"
              : "This document is already uploaded. Overwrite it?"}
          </DialogDescription>
        </DialogHeader>
        <p className="truncate text-sm">{files.map((file) => file.name).join(", ")}</p>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onOverwrite}>Overwrite</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
