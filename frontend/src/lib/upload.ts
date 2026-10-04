// Same limit as MAX_UPLOAD_MB in env/config.py (nginx.conf allows it plus the multipart wrapping).
export const MAX_UPLOAD_MB = 10

const BYTES_PER_MB = 1024 * 1024

// Returns a message when the browser can already tell the backend would reject the file.
export function checkFile(file: File): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
  if (!isPdf) return `${file.name} is not a PDF.`
  if (file.size > MAX_UPLOAD_MB * BYTES_PER_MB) {
    return `${file.name} is larger than ${MAX_UPLOAD_MB} MB.`
  }
  return null
}
