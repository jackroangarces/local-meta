import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <header className="site-navbar">
      <nav className="site-navbar__inner">
        <Link to="/" className="site-navbar__link">
          Home
        </Link>
      </nav>
    </header>
  );
}
