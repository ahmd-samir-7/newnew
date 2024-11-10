const API_URL = 'http://localhost:3001/api';

export const getTasks = async () => {
  const response = await fetch(`${API_URL}/tasks`);
  return response.json();
};

export const createTask = async (title) => {
  const response = await fetch(`${API_URL}/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title }),
  });
  return response.json();
};

export const toggleTask = async (id) => {
  const response = await fetch(`${API_URL}/tasks/${id}`, {
    method: 'PUT',
  });
  return response.json();
};

export const deleteTask = async (id) => {
  await fetch(`${API_URL}/tasks/${id}`, {
    method: 'DELETE',
  });
};