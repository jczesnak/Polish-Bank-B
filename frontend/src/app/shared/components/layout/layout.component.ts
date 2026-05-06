import { Component, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NgIf, NgFor, NgClass, DatePipe } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgIf, NgFor, NgClass, DatePipe],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css'
})
export class LayoutComponent {
  private auth = inject(AuthService);
  protected notifSvc = inject(NotificationService);
  readonly user = this.auth.user;
  showNotifications = signal(false);

  pageTitle() {
    const path = window.location.pathname;
    if (path.includes('settings')) return 'Ustawienia';
    if (path.includes('dashboard')) return 'Pulpit';
    return 'TotalBank';
  }

  toggleNotifications() {
    const next = !this.showNotifications();
    this.showNotifications.set(next);
    if (next) this.notifSvc.markAllRead();
  }

  logout() {
    this.auth.logout();
  }
}
