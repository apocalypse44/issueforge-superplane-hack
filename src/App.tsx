import React, { useState } from 'react';
import MarkdownRenderer from './components/MarkdownRenderer';

function App() {
  const [markdownText, setMarkdownText] = useState('');
  const [EditMode, setEditMode] = useState(false);

  const handleToggleEditMode = () => {
    setEditMode(!EditMode);
  };

  return (
    <div>
      {EditMode ? (
        <textarea
          value={markdownText}
          onChange={(e) => setMarkdownText(e.target.value)}
          placeholder="Enter Markdown text"
        />
      ) : (
        <MarkdownRenderer markdownText={markdownText} />
      )}
      <button onClick={handleToggleEditMode}>{EditMode ? 'View Mode' : 'Edit Mode'}</button>
    </div>
  );
}

export default App;