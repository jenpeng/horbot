import Empty from '../ui/Empty';

interface PanelEmptyStateProps {
  title: string;
  description: string;
}

const PanelEmptyState = ({
  title,
  description,
}: PanelEmptyStateProps) => (
  <Empty
    title={title}
    description={description}
    className="py-10"
  />
);

export default PanelEmptyState;
