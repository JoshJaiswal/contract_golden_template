import { getFileExtension } from '@/lib/format';
import { AudioPreview } from './AudioPreview';
import { PdfPreview } from './PdfPreview';
import { SourcePreview } from './SourcePreview';

export function PreviewPane({
  jobId,
  fileName,
}: {
  jobId: string;
  fileName: string;
}) {
  const ext = getFileExtension(fileName);

  if (ext === '.mp3' || ext === '.wav' || ext === '.m4a') {
    return <AudioPreview jobId={jobId} />;
  }

  if (ext === '.pdf') {
    return <PdfPreview jobId={jobId} />;
  }

  return <SourcePreview jobId={jobId} />;
}