import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TransferService } from '../../core/services/transfer.service';

@Component({
  selector: 'app-transfer',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './transfer.component.html',
})
export class TransferComponent implements OnInit {
  transferForm!: FormGroup;
  isLoading = false;
  successMessage = '';
  errorMessage = '';

  constructor(
    private fb: FormBuilder,
    private transferService: TransferService,
    private router: Router
  ) {}

  ngOnInit(): void {

    this.transferForm = this.fb.group({

      sender_account: ['', Validators.required], 
      recipient_iban: ['', [Validators.required, Validators.minLength(26)]],
      recipient_name: ['', Validators.required],
      amount: [null, [Validators.required, Validators.min(0.01)]],
      title: ['', Validators.required]
    });
  }

  onSubmit(): void {
    if (this.transferForm.invalid) {
      this.transferForm.markAllAsTouched();
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';
    this.successMessage = '';

    this.transferService.createInternalTransfer(this.transferForm.value).subscribe({
      next: (response) => {
        this.isLoading = false;
        this.successMessage = 'Przelew zrealizowany natychmiastowo!';
        this.transferForm.reset();
        
   
        setTimeout(() => {
          this.router.navigate(['/dashboard']);
        }, 2000);
      },
      error: (err) => {
        this.isLoading = false;

        this.errorMessage = err.error?.error 
          || err.error?.amount?.[0] 
          || err.error?.recipient_iban?.[0] 
          || 'Wystąpił błąd podczas realizacji przelewu.';
      }
    });
  }
}