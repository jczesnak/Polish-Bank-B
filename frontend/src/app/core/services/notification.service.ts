import { Injectable, signal, computed } from '@angular/core';

export interface AppNotification {
  id: string;
  message: string;
  type: 'in' | 'out';
  time: Date;
  read: boolean;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private _items = signal<AppNotification[]>([]);
  readonly items = this._items.asReadonly();
  readonly unreadCount = computed(() => this._items().filter(n => !n.read).length);

  add(message: string, type: 'in' | 'out') {
    const notification: AppNotification = {
      id: Date.now().toString(),
      message,
      type,
      time: new Date(),
      read: false,
    };
    this._items.update(list => [notification, ...list].slice(0, 20));
  }

  markAllRead() {
    this._items.update(list => list.map(n => ({ ...n, read: true })));
  }

  clear() {
    this._items.set([]);
  }
}
