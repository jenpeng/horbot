import { PageErrorState } from '../state';

const DashboardErrorState = ({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) => <PageErrorState error={error} onRetry={onRetry} />;

export default DashboardErrorState;
