import React from 'react';

const TailwindTest = () => {
  return (
    <div className="p-8 bg-red-500 text-white rounded-lg shadow-lg max-w-md mx-auto mt-8">
      <h1 className="text-2xl font-bold mb-4">Tailwind CSS Test</h1>
      <p className="text-lg">If you can see this styled with a red background, white text, padding, and rounded corners, then Tailwind CSS is working correctly!</p>
      <div className="mt-4 space-y-2">
        <div className="bg-blue-500 p-2 rounded">Blue background</div>
        <div className="bg-green-500 p-2 rounded">Green background</div>
        <div className="bg-yellow-500 p-2 rounded text-black">Yellow background</div>
      </div>
    </div>
  );
};

export default TailwindTest;