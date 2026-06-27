import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import mermaid from 'mermaid';

interface Props {
  markdownText: string;
}

const MarkdownRenderer: React.FC<Props> = ({ markdownText }) => {
  return (
    <div>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {markdownText}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;