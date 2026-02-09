import './Testing.css';
import { useContext } from 'react';
import { DataContext } from '../DataContext';

function Testing() {
  const { parsedData } = useContext(DataContext);

  if (!parsedData) return <div className="testing-container">No data to display. Please upload a file first.</div>;
  
  return (
    <div className="testing-container">
      <h2>This is the scraped data from the uploaded file:</h2>

      <pre className="parsed-data">
        {parsedData?.text}
      </pre>
    </div>
  );
}

export default Testing;