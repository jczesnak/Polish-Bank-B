import { Component, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NgIf, NgFor, NgClass, DatePipe } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';

import { HttpClient } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

export interface BlikTransaction {
  id: string;
  klik_transaction_id: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
  merchant_name: string;
  needs_parent_auth?: boolean;
  junior_user_name?: string;
}

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgIf, NgFor, NgClass, DatePipe, ReactiveFormsModule],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css'
})
export class LayoutComponent {
  private auth = inject(AuthService);
  protected notifSvc = inject(NotificationService);
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);
  readonly user = this.auth.user;
  showNotifications = signal(false);

  pendingBlikTransaction = signal<BlikTransaction | null>(null);
  showBlikModal = signal(false);
  blikAuthForm = this.fb.group({ pin: ['', [Validators.required, Validators.pattern('^[0-9]{4}$')]] });
  blikAuthLoading = signal(false);
  blikAuthError = signal('');
  pollingInterval: any;

  ngOnInit() {
    this.pollingInterval = setInterval(() => {
      this.pollPendingTransactions();
    }, 3000);
  }

  ngOnDestroy() {
    if (this.pollingInterval) clearInterval(this.pollingInterval);
  }

  pollPendingTransactions() {
    if (!this.user()) return;
    this.http.get<BlikTransaction[]>('/api/blik/transactions/').subscribe({
      next: (txs) => {
        const pending = txs.find(t => t.status === 'PENDING');
        if (pending && !this.pendingBlikTransaction()) {
          this.pendingBlikTransaction.set(pending);
          const msg = pending.needs_parent_auth && pending.junior_user_name
            ? `Nowa transakcja BLIK do potwierdzenia z konta Junior ${pending.junior_user_name}: ${pending.amount} PLN`
            : `Oczekująca płatność BLIK: ${pending.amount} PLN`;
          this.notifSvc.add(msg, 'in');
        } else if (!pending && this.pendingBlikTransaction()) {
          this.pendingBlikTransaction.set(null);
          this.showBlikModal.set(false);
        }
      }
    });
  }

  openBlikModal() {
    this.showNotifications.set(false);
    this.showBlikModal.set(true);
    this.blikAuthForm.reset();
  }

  authorizeBlikTransaction() {
    if (this.blikAuthForm.invalid || !this.pendingBlikTransaction()) return;
    this.blikAuthLoading.set(true);
    this.blikAuthError.set('');

    this.http.post(`/api/blik/transactions/${this.pendingBlikTransaction()?.id}/authorize/`, this.blikAuthForm.value).subscribe({
      next: () => {
        this.blikAuthLoading.set(false);
        this.pendingBlikTransaction.set(null);
        this.showBlikModal.set(false);
        this.notifSvc.add('Transakcja BLIK autoryzowana pomyślnie!', 'in');
      },
      error: (err) => {
        this.blikAuthLoading.set(false);
        this.blikAuthError.set(err.error?.pin || err.error?.detail || 'Błąd autoryzacji.');
      }
    });
  }

  rejectBlikTransaction() {
    if (!this.pendingBlikTransaction()) return;
    this.blikAuthLoading.set(true);
    this.blikAuthError.set('');

    this.http.post(`/api/blik/transactions/${this.pendingBlikTransaction()?.id}/reject/`, {}).subscribe({
      next: () => {
        this.blikAuthLoading.set(false);
        this.pendingBlikTransaction.set(null);
        this.showBlikModal.set(false);
        this.notifSvc.add('Transakcja BLIK została odrzucona.', 'out');
      },
      error: (err) => {
        this.blikAuthLoading.set(false);
        this.blikAuthError.set('Błąd odrzucania transakcji.');
      }
    });
  }

  pageTitle() {
    const path = window.location.pathname;
    if (path.includes('settings')) return 'Ustawienia';
    if (path.includes('dashboard')) return 'Pulpit';
    if (path.includes('p2p')) return 'Przelew na telefon';
    if (path.includes('transfer')) return 'Przelew';
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
