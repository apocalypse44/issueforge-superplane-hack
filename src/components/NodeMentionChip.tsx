import React from 'react';

interface Props {
  node: string;
}

const NodeMentionChip: React.FC<Props> = ({ node }) => {
  return (
    <div>
      <span>{node}</span>
    </div>
  );
};

export default NodeMentionChip;