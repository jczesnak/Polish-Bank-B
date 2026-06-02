import { Component, OnDestroy, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NgIf, NgFor, NgClass, DatePipe } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';
import { RealtimeService } from '../../../core/services/realtime.service';
import { ApprovalRequest, JuniorService } from '../../../core/services/junior.service';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgIf, NgFor, NgClass, DatePipe],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css'
})
export class LayoutComponent implements OnDestroy {
  private auth = inject(AuthService);
  protected notifSvc = inject(NotificationService);
  private realtime = inject(RealtimeService);
  private junior = inject(JuniorService);
  readonly user = this.auth.user;
  showNotifications = signal(false);
  approvals = signal<ApprovalRequest[]>([]);
  approvalError = signal('');
  decidingApprovalId = signal<string | null>(null);
  private approvalPoller: any;

  constructor() {
    this.realtime.connect();
    if (this.user()?.role !== 'JUNIOR') this.loadApprovals();
    this.realtime.events$.subscribe((event) => {
      if (event.event === 'approval.created') this.loadApprovals();
    });
    if (this.user()?.role !== 'JUNIOR') {
      this.approvalPoller = setInterval(() => this.loadApprovals(false), 5000);
    }
  }

  ngOnDestroy() {
    if (this.approvalPoller) clearInterval(this.approvalPoller);
  }

  pageTitle() {
    const path = window.location.pathname;
    if (path.includes('settings')) return 'Ustawienia';
    if (path.includes('junior-payments')) return 'Płatności';
    if (path.includes('junior-dashboard')) return 'Panel Juniora';
    if (path.includes('junior')) return 'Konto Junior';
    if (path.includes('dashboard')) return 'Pulpit';
    if (path.includes('p2p')) return 'Przelew na telefon';
    if (path.includes('transfer')) return 'Przelew';
    return 'TotalBank';
  }

  toggleNotifications() {
    const next = !this.showNotifications();
    this.showNotifications.set(next);
    if (next) {
      this.notifSvc.markAllRead();
      if (this.user()?.role !== 'JUNIOR') this.loadApprovals();
    }
  }

  pendingApprovals() {
    return this.approvals().filter((approval) => approval.status === 'PENDING');
  }

  approvalBadgeCount() {
    return this.pendingApprovals().length + this.notifSvc.unreadCount();
  }

  loadApprovals(showError = true) {
    this.junior.listApprovals().subscribe({
      next: (approvals) => {
        this.approvals.set(approvals);
        this.approvalError.set('');
      },
      error: () => {
        if (showError) this.approvalError.set('Nie udało się pobrać zgód.');
      },
    });
  }

  approve(approval: ApprovalRequest, event: Event) {
    event.preventDefault();
    event.stopPropagation();
    this.decidingApprovalId.set(approval.id);
    this.approvalError.set('');
    this.junior.approve(approval.id).subscribe({
      next: () => {
        this.decidingApprovalId.set(null);
        this.loadApprovals();
      },
      error: (err) => {
        this.decidingApprovalId.set(null);
        this.approvalError.set(err?.error?.detail || err?.error?.amount || 'Nie udało się zaakceptować transakcji.');
      },
    });
  }

  reject(approval: ApprovalRequest, event: Event) {
    event.preventDefault();
    event.stopPropagation();
    this.decidingApprovalId.set(approval.id);
    this.approvalError.set('');
    this.junior.reject(approval.id).subscribe({
      next: () => {
        this.decidingApprovalId.set(null);
        this.loadApprovals();
      },
      error: (err) => {
        this.decidingApprovalId.set(null);
        this.approvalError.set(err?.error?.detail || 'Nie udało się odrzucić transakcji.');
      },
    });
  }

  logout() {
    this.auth.logout();
  }
}
