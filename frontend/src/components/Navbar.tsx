import { Link } from "react-router-dom";
import logoUrl from "../assets/local_meta_logo.png";

export default function Navbar() {
  return (
    <header className="site-navbar">
      <div className="site-navbar__backdrop" aria-hidden />
      <nav className="site-navbar__inner">
        <Link to="/" className="site-navbar__brand">
          <img src={logoUrl} alt="Local Meta" className="site-navbar__logo" />
        </Link>
      </nav>
    </header>
  );
}
