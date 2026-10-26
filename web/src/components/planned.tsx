import type { ReactNode } from 'react';
import { Card, CardHeader, CardBody, MaturityBadge } from './ui';
import { useStation } from '../api/station';

/**
 * A feature with no station endpoint yet. With demo data the preview
 * (children) is shown under the demo banner; with a live station the panel
 * says the feature is not available instead of showing synthetic values.
 */
export function Planned({ title, needs, children }: { title: string; needs: string; children: ReactNode }) {
  const { isDemo } = useStation();
  if (isDemo) return <>{children}</>;
  return (
    <Card>
      <CardHeader title={title} badge={<MaturityBadge level="planned" />} />
      <CardBody>
        <div className="text-[11px]" style={{ color:'var(--t3)' }}>Not available from this station yet.</div>
        <div className="text-[10px] mt-1" style={{ color:'var(--t3)' }}>Needs: {needs}</div>
      </CardBody>
    </Card>
  );
}

/** Inline error line for a failed endpoint (the last good value, if any, stays on screen). */
export function ApiErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <div className="text-[10px] mono px-2 py-1 rounded-[2px] mb-2"
      style={{ color:'var(--err-text)', background:'var(--err-bg)', border:'1px solid var(--err-border)' }}>
      {error}
    </div>
  );
}
