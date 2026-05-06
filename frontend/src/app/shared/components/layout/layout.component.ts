import { Component, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { NgIf } from '@angular/common';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgIf],
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.css'
})
export class LayoutComponent {
  private auth = inject(AuthService);
  readonly user = this.auth.user;

  pageTitle() {
    const path = window.location.pathname;
    if (path.includes('settings')) return 'Ustawienia';
    if (path.includes('dashboard')) return 'Pulpit';
    return 'TotalBank'; // <-- Zmieniona nazwa
  }

  logout() {
    this.auth.logout();
  }
}