import { CommonModule, DatePipe, DecimalPipe, NgClass } from '@angular/common';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subscription } from 'rxjs';
import {
  ApprovalRequest,
  BankAccount,
  JuniorActivity,
  JuniorOperation,
  JuniorService,
} from '../../core/services/junior.service';
import { RealtimeService } from '../../core/services/realtime.service';

type HistoryFilter = 'all' | 'expenses' | 'income' | 'pending' | 'blik';

@Component({
  selector: 'app-junior-parent',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, DatePipe, DecimalPipe, NgClass],
  templateUrl: './junior-parent.component.html',
})
export class JuniorParentComponent implements OnInit, OnDestroy {
  private fb = inject(FormBuilder);
  private junior = inject(JuniorService);
  private realtime = inject(RealtimeService);
  private sub?: Subscription;
  private approvalPoller: ReturnType<typeof setInterval> | null = null;

  parentAccounts = signal<BankAccount[]>([]);
  juniorAccounts = signal<BankAccount[]>([]);
  approvals = signal<ApprovalRequest[]>([]);
  selectedJuniorId = signal<string | null>(null);
  selectedActivity = signal<JuniorActivity | null>(null);
  activityLoading = signal(false);
  historyFilter = signal<HistoryFilter>('all');
  loading = signal(false);
  message = signal('');
  error = signal('');
  approvalActionMessage = signal('');
  approvalActionError = signal('');

  readonly historyFilters: { key: HistoryFilter; label: string }[] = [
    { key: 'all', label: 'Wszystkie' },
    { key: 'expenses', label: 'Wydatki' },
    { key: 'income', label: 'Wpływy' },
    { key: 'blik', label: 'BLIK' },
    { key: 'pending', label: 'Oczekujące' },
  ];

  readonly filteredOperations = computed(() => {
    const activity = this.selectedActivity();
    if (!activity) return [] as JuniorOperation[];

    const filter = this.historyFilter();
    const operations = activity.operations;

    if (filter === 'expenses') {
      return operations.filter(
        (op) => op.direction === 'OUT' && !this.isPendingOperation(op),
      );
    }
    if (filter === 'income') {
      return operations.filter((op) => op.direction === 'IN');
    }
    if (filter === 'pending') {
      return operations.filter((op) => this.isPendingOperation(op));
    }
    if (filter === 'blik') {
      return operations.filter((op) => op.kind === 'BLIK');
    }
    return operations;
  });

  readonly historyCounts = computed(() => {
    const activity = this.selectedActivity();
    if (!activity) {
      return { all: 0, expenses: 0, income: 0, pending: 0, blik: 0 };
    }

    const operations = activity.operations;
    return {
      all: operations.length,
      expenses: operations.filter(
        (op) => op.direction === 'OUT' && !this.isPendingOperation(op),
      ).length,
      income: operations.filter((op) => op.direction === 'IN').length,
      pending: operations.filter((op) => this.isPendingOperation(op)).length,
      blik: operations.filter((op) => op.kind === 'BLIK').length,
    };
  });

  form = this.fb.group({
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    pesel: ['', [Validators.required, Validators.pattern(/^\d{11}$/)]],
    phone_number: ['', Validators.pattern(/^\d{9}$/)],
    password: ['', [Validators.required, Validators.minLength(8)]],
    password_confirm: ['', Validators.required],
    parent_account_id: ['', Validators.required],
  });

  ngOnInit() {
    this.loadAll();
    this.realtime.connect();
    this.sub = this.realtime.events$.subscribe((event) => {
      if (event.event === 'approval.created') this.loadApprovals();
      if (
        event.event.startsWith('approval.') &&
        this.selectedJuniorId()
      ) {
        this.loadActivityById(this.selectedJuniorId()!);
      }
    });
    this.approvalPoller = setInterval(() => this.loadApprovals(), 5000);
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    if (this.approvalPoller) clearInterval(this.approvalPoller);
  }

  loadAll() {
    this.junior.listAccounts().subscribe((accounts) => {
      const parentAccounts = accounts.filter((a) => a.account_type !== 'JUNIOR');
      this.parentAccounts.set(parentAccounts);
      if (parentAccounts.length && !this.form.value.parent_account_id) {
        this.form.patchValue({ parent_account_id: parentAccounts[0].id });
      }
    });
    this.loadJuniors();
    this.loadApprovals();
  }

  loadJuniors() {
    this.junior.listJuniors().subscribe((accounts) => {
      this.juniorAccounts.set(accounts);
      if (accounts.length && !this.selectedJuniorId()) {
        this.loadActivity(accounts[0]);
      }
    });
  }

  loadApprovals() {
    this.junior.listApprovals().subscribe((approvals) => this.approvals.set(approvals));
  }

  pendingApprovals() {
    return this.approvals().filter((approval) => approval.status === 'PENDING');
  }

  pendingBlikApprovals() {
    return this.pendingApprovals().filter((a) => a.request_type === 'BLIK_PAYMENT');
  }

  approvalIcon(approval: ApprovalRequest) {
    if (approval.request_type === 'BLIK_PAYMENT') return '🎲';
    if (approval.request_type === 'CARD_PAYMENT') return '💳';
    return '💸';
  }

  approve(approval: ApprovalRequest) {
    this.approvalActionError.set('');
    this.junior.approve(approval.id).subscribe({
      next: () => {
        this.approvalActionMessage.set(
          approval.request_type === 'BLIK_PAYMENT'
            ? 'Płatność BLIK dziecka została autoryzowana.'
            : 'Transakcja zaakceptowana.',
        );
        this.loadApprovals();
        if (this.selectedJuniorId()) this.loadActivityById(this.selectedJuniorId()!);
      },
      error: (err) => this.approvalActionError.set(this.extractError(err, 'Nie udało się zaakceptować transakcji.')),
    });
  }

  reject(approval: ApprovalRequest) {
    this.approvalActionError.set('');
    this.junior.reject(approval.id).subscribe({
      next: () => {
        this.approvalActionMessage.set(
          approval.request_type === 'BLIK_PAYMENT'
            ? 'Płatność BLIK dziecka została odrzucona.'
            : 'Transakcja odrzucona.',
        );
        this.loadApprovals();
        if (this.selectedJuniorId()) this.loadActivityById(this.selectedJuniorId()!);
      },
      error: (err) => this.approvalActionError.set(this.extractError(err, 'Nie udało się odrzucić transakcji.')),
    });
  }

  createJunior() {
    if (this.passwordsMismatch()) {
      this.form.get('password_confirm')?.setErrors({ mismatch: true });
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.message.set('');
    this.junior.createJunior(this.form.value as any).subscribe({
      next: (result) => {
        this.loading.set(false);
        this.message.set('Konto Junior zostało utworzone razem z kartą prepaid.');
        this.form.patchValue({
          first_name: '',
          last_name: '',
          email: '',
          pesel: '',
          phone_number: '',
          password: '',
          password_confirm: '',
        });
        this.loadJuniors();
        this.loadActivity(result.account);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(this.extractError(err, 'Nie udało się utworzyć konta Junior.'));
      },
    });
  }

  loadActivity(account: BankAccount) {
    this.selectedJuniorId.set(account.id);
    this.historyFilter.set('all');
    this.loadActivityById(account.id);
  }

  loadActivityById(accountId: string) {
    this.activityLoading.set(true);
    this.junior.getJuniorActivity(accountId).subscribe({
      next: (activity) => {
        this.selectedActivity.set(activity);
        this.activityLoading.set(false);
      },
      error: () => {
        this.activityLoading.set(false);
        this.error.set('Nie udało się pobrać historii wydatków dziecka.');
      },
    });
  }

  isSelectedJunior(account: BankAccount) {
    return this.selectedJuniorId() === account.id;
  }

  isPendingOperation(op: JuniorOperation) {
    return ['PENDING', 'PENDING_APPROVAL', 'AUTHORIZED'].includes(op.status);
  }

  blikStatusLabel(status: string, rejectReason?: string) {
    if (status === 'COMPLETED') return 'Zrealizowana';
    if (status === 'REJECTED') return rejectReason ? `Odrzucona · ${rejectReason}` : 'Odrzucona';
    if (status === 'TIMEOUT') return 'Timeout';
    if (status === 'AUTHORIZED') return 'Autoryzowana';
    return 'Oczekująca';
  }

  blikRejectLabel(reason?: string) {
    const labels: Record<string, string> = {
      INSUFFICIENT_FUNDS: 'Brak środków',
      USER_DECLINED: 'Odrzucono przez użytkownika',
      AML_BLOCK: 'Blokada AML',
      OTHER: 'Inny powód',
    };
    return reason ? labels[reason] || reason : '';
  }

  operationIcon(op: JuniorOperation) {
    if (op.kind === 'BLIK') return '🎲';
    if (op.kind === 'CARD') return '💳';
    return op.direction === 'IN' ? '↓' : '↑';
  }

  fieldInvalid(field: string) {
    const control = this.form.get(field);
    return !!control && control.invalid && (control.touched || control.dirty);
  }

  passwordsMismatch() {
    const password = this.form.value.password || '';
    const confirmation = this.form.value.password_confirm || '';
    return !!password && !!confirmation && password !== confirmation;
  }

  canCreateJunior() {
    return this.form.valid && !this.passwordsMismatch() && this.parentAccounts().length > 0 && !this.loading();
  }

  private extractError(err: any, fallback: string) {
    const data = err?.error;
    if (data?.detail) return data.detail;
    if (typeof data === 'object' && data) return Object.values(data).flat().join(' ');
    return fallback;
  }
}
