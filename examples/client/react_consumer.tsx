// React example: Consumer for StreamWeaver SSE events
import { useEffect, useState } from 'react';

interface StreamEvent {
  type: string;
  sessionId: string;
  timestamp: number;
  step?: number;
  message: string;
  data?: any;
  progress?: number;
  tool?: string;
  success?: boolean;
  metadata?: any;
}

interface AgentStreamProps {
  sessionId: string;
}

export function AgentStream({ sessionId }: AgentStreamProps) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(`/stream/${sessionId}`);
    
    eventSource.onopen = () => {
      setConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);
        setEvents(prev => [...prev, data]);
      } catch (err) {
        console.error('Failed to parse event:', err);
      }
    };

    eventSource.onerror = (err) => {
      setConnected(false);
      setError('Connection error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [sessionId]);

  const closeStream = async () => {
    try {
      await fetch(`/stream/${sessionId}/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, reason: 'User requested' })
      });
    } catch (err) {
      console.error('Failed to close stream:', err);
    }
  };

  return (
    <div className="agent-stream">
      <div className="status-bar">
        <span>Session: {sessionId}</span>
        <span>Status: {connected ? 'Connected' : 'Disconnected'}</span>
        {connected && (
          <button onClick={closeStream}>Close Stream</button>
        )}
      </div>

      {error && (
        <div className="error">Error: {error}</div>
      )}

      <div className="events">
        {events.map((event, index) => (
          <div key={index} className={`event event-${event.type}`}>
            <div className="event-header">
              <span className="event-type">{event.type}</span>
              {event.step && <span className="event-step">Step {event.step}</span>}
              {event.progress !== undefined && (
                <span className="event-progress">{event.progress.toFixed(0)}%</span>
              )}
            </div>
            <div className="event-message">{event.message}</div>
            {event.data && (
              <div className="event-data">
                <pre>{JSON.stringify(event.data, null, 2)}</pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
