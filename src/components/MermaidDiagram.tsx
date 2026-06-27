import React, { useEffect, useState } from 'react';
import mermaid from 'mermaid';

interface Props {
  diagram: string;
}

const MermaidDiagram: React.FC<Props> = ({ diagram }) => {
  const [svg, setSvg] = useState('');

  useEffect(() => {
    const renderDiagram = async () => {
      const svgCode = await mermaid.render('diagram', diagram);
      setSvg(svgCode);
    };
    renderDiagram();
  }, [diagram]);

  return (
    <div
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
};

export default MermaidDiagram;