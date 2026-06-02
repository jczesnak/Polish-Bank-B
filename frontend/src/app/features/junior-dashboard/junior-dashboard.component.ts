import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { JuniorService, BankAccount } from '../../core/services/junior.service';
import { RealtimeService } from '../../core/services/realtime.service';

@Component({
  selector: 'app-junior-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './junior-dashboard.component.html',
})
export class JuniorDashboardComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private router = inject(Router);
  private junior = inject(JuniorService);
  private realtime = inject(RealtimeService);
  private sub?: Subscription;

  account = signal<BankAccount | null>(null);
  blikCode = signal<string | null>(null);
  blikTimeLeft = signal(0);
  blikLoading = signal(false);
  message = signal('');
  error = signal('');
  pendingBlik = signal<{ merchant_name: string; amount: string } | null>(null);
  private blikInterval: ReturnType<typeof setInterval> | null = null;
  private blikPendingPoller: ReturnType<typeof setInterval> | null = null;

  ngOnInit() {
    this.load();
    this.realtime.connect();
    this.sub = this.realtime.events$.subscribe((event) => {
      if (event.event === 'approval.approved' || event.event === 'approval.rejected') {
        this.message.set(
          event.event === 'approval.approved'
            ? 'Rodzic zaakceptował transakcję!'
            : 'Rodzic odrzucił transakcję.',
        );
        this.load();
        this.loadPendingBlik();
      }
    });
    this.loadPendingBlik();
    this.blikPendingPoller = setInterval(() => this.loadPendingBlik(), 4000);
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    if (this.blikInterval) clearInterval(this.blikInterval);
    if (this.blikPendingPoller) clearInterval(this.blikPendingPoller);
  }

  loadPendingBlik() {
    this.http.get<{ merchant_name: string; amount: string; status: string }[]>('/api/blik/transactions/').subscribe({
      next: (txs) => {
        const pending = txs.find((tx) => tx.status === 'PENDING');
        this.pendingBlik.set(pending ? { merchant_name: pending.merchant_name, amount: pending.amount } : null);
      },
    });
  }

  load() {
    this.junior.listAccounts().subscribe((accounts) => {
      this.account.set(accounts.find((a) => a.account_type === 'JUNIOR') || null);
    });
  }

  goToPayments() {
    void this.router.navigate(['/junior-payments']);
  }

  generateBlik() {
    const account = this.account();
    if (!account) return;
    if (this.blikInterval) clearInterval(this.blikInterval);
    this.error.set('');
    this.blikCode.set(null);
    this.blikLoading.set(true);

    this.http.post<{ code: string; expires_in: number }>('/api/blik/generate/', { account_id: account.id }).subscribe({
      next: (res) => {
        this.blikCode.set(res.code);
        this.blikTimeLeft.set(res.expires_in ?? 120);
        this.blikLoading.set(false);
        this.blikInterval = setInterval(() => {
          this.blikTimeLeft.update((time) => Math.max(time - 1, 0));
          if (this.blikTimeLeft() <= 0) {
            clearInterval(this.blikInterval);
            this.blikCode.set(null);
          }
        }, 1000);
      },
      error: (err) => {
        this.blikLoading.set(false);
        this.error.set(this.extractError(err, 'Nie udało się wygenerować kodu BLIK.'));
      },
    });
  }

  private extractError(err: any, fallback: string) {
    const data = err?.error;
    if (data?.detail) return data.detail;
    if (typeof data === 'object' && data) return Object.values(data).flat().join(' ');
    return fallback;
  }
}
