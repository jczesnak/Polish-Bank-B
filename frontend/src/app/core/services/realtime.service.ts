import { Injectable, inject } from '@angular/core';
import { Subject } from 'rxjs';
import { AuthService } from './auth.service';
import { NotificationService } from './notification.service';

export interface RealtimeEvent {
  event: string;
  payload: any;
}

@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private auth = inject(AuthService);
  private notifications = inject(NotificationService);
  private socket: WebSocket | null = null;
  private reconnectTimer: any;
  private eventsSubject = new Subject<RealtimeEvent>();
  readonly events$ = this.eventsSubject.asObservable();

  connect() {
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)
    ) return;
    const token = this.auth.getAccessToken();
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    this.socket = new WebSocket(`${protocol}://${window.location.host}/ws/notifications/?token=${token}`);
    this.socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as RealtimeEvent;
      this.eventsSubject.next(event);
      if (event.event === 'approval.created') {
        this.notifications.add(
          `Nowa prośba o zgodę${event.payload.type === 'BLIK_PAYMENT' ? ' (BLIK)' : ''}: ${event.payload.amount} PLN → ${event.payload.target}`,
          'out',
        );
      }
      if (event.event === 'approval.approved') {
        this.notifications.add('Rodzic zaakceptował Twoją transakcję.', 'in');
      }
      if (event.event === 'approval.rejected') {
        this.notifications.add('Rodzic odrzucił Twoją transakcję.', 'out');
      }
      if (event.event === 'blik.pending') {
        this.notifications.add(
          `Autoryzuj płatność BLIK: ${event.payload.amount} PLN`,
          'out',
        );
      }
    };
    this.socket.onclose = () => {
      this.socket = null;
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };
    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close();
    this.socket = null;
  }
}
