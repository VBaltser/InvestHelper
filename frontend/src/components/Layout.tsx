import { NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="app-shell">
      <header className="header">
        <div className="header-brand">
          <h1>InvestHelper</h1>
          <nav className="nav">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `nav-link${isActive ? " active" : ""}`
              }
            >
              Портфель
            </NavLink>
            <NavLink
              to="/operations"
              className={({ isActive }) =>
                `nav-link${isActive ? " active" : ""}`
              }
            >
              Операции
            </NavLink>
            <NavLink
              to="/bonds"
              className={({ isActive }) =>
                `nav-link${isActive ? " active" : ""}`
              }
            >
              Скринер облигаций
            </NavLink>
            <NavLink
              to="/dfa"
              className={({ isActive }) =>
                `nav-link${isActive ? " active" : ""}`
              }
            >
              Скринер долговых ЦФА
            </NavLink>
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
