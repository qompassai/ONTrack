use pyo3::prelude::*;

#[pyfunction]
fn solve_greedy(matrix: Vec<f64>, n: usize) -> PyResult<Vec<usize>> {
    if n == 0 || matrix.len() != n * n {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "matrix must be n×n flat list",
        ));
    }
    let mut visited = vec![false; n];
    let mut route = Vec::with_capacity(n);
    let mut current = 0usize;
    visited[current] = true;
    route.push(current);

    for _ in 1..n {
        let mut best_dist = f64::INFINITY;
        let mut best_next = 0usize;
        for next in 0..n {
            if !visited[next] {
                let d = matrix[current * n + next];
                if d < best_dist {
                    best_dist = d;
                    best_next = next;
                }
            }
        }
        visited[best_next] = true;
        route.push(best_next);
        current = best_next;
    }
    Ok(route)
}

#[pyfunction]
fn haversine_matrix(coords: Vec<(f64, f64)>) -> PyResult<Vec<f64>> {
    let n = coords.len();
    let mut mat = vec![0.0f64; n * n];
    for i in 0..n {
        for j in (i + 1)..n {
            let d = haversine(coords[i].0, coords[i].1, coords[j].0, coords[j].1);
            mat[i * n + j] = d;
            mat[j * n + i] = d;
        }
    }
    Ok(mat)
}

fn haversine(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let r = 6_371_000.0_f64; // metres
    let dlat = (lat2 - lat1).to_radians();
    let dlon = (lon2 - lon1).to_radians();
    let a = (dlat / 2.0).sin().powi(2)
        + lat1.to_radians().cos() * lat2.to_radians().cos() * (dlon / 2.0).sin().powi(2);
    2.0 * r * a.sqrt().asin()
}

#[pymodule]
fn ontrack(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(solve_greedy, m)?)?;
    m.add_function(wrap_pyfunction!(haversine_matrix, m)?)?;
    Ok(())
}

