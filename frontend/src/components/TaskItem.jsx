import React from 'react';
import { Button } from '@/components/ui/button';
import { Trash2 } from 'lucide-react';

const TaskItem = ({ task, onToggle, onDelete }) => {
  return (
    <div className="flex items-center justify-between p-3 bg-white border rounded-lg">
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          checked={task.completed}
          onChange={() => onToggle(task.id)}
          className="w-4 h-4"
        />
        <span className={task.completed ? 'line-through text-gray-500' : ''}>
          {task.title}
        </span>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onDelete(task.id)}
        className="text-red-500 hover:text-red-700"
      >
        <Trash2 className="w-4 h-4" />
      </Button>
    </div>
  );
};

export default TaskItem;