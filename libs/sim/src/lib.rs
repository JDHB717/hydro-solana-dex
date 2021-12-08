use pyo3::prelude::*;
use pyo3::types::PyTuple;
use spl_math::precise_number::PreciseNumber;
use spl_math::uint::U256;
use std::fs::File;
use std::io::prelude::*;

type InnerUint = U256;

const FILE_NAME: &str = "simulation.py";
const FILE_PATH: &str = "../sim/simulation.py";
const MODULE_NAME: &str = "simulation";

pub struct Model {
    py_src: String,
    pub x0: u128,
    pub y0: u128,
    pub c_numer: u128,
    pub c_denom: u128,
    pub i: u128,
}

impl Model {
    pub fn new(x0: u128, y0: u128, c_numer: u128, c_denom: u128, i: u128) -> Model {
        let src_file = File::open(FILE_PATH);
        let mut src_file = match src_file {
            Ok(file) => file,
            Err(error) => {
                panic!("{:?}\n Please copy https://colab.research.google.com/drive/1TsWxjrkqiHQD9PU4V-RCX9hmMZKuEuBb?usp=sharing into sim/simulation.py`", error)
            }
        };
        let mut src_content = String::new();
        let _ = src_file.read_to_string(&mut src_content);

        Self {
            py_src: src_content,
            x0,
            y0,
            c_numer,
            c_denom,
            i,
        }
    }

    pub fn sim_k(&self) -> PreciseNumber {
        let gil = Python::acquire_gil();
        let result: u128 = self
            .call0(gil.python(), "sim_k")
            .unwrap()
            .extract(gil.python())
            .unwrap();
        let precise_number = PreciseNumber::new(result).unwrap();
        return precise_number;
    }

    pub fn sim_xi(&self) -> (PreciseNumber, bool) {
        let gil = Python::acquire_gil();
        let result: (u128, bool) = self
            .call0(gil.python(), "sim_xi")
            .unwrap()
            .extract(gil.python())
            .unwrap();
        let precise_number = PreciseNumber {
            value: InnerUint::from(result.0),
        };
        let is_signed = result.1;
        return (precise_number, is_signed);
    }

    pub fn sim_delta_y_amm(&self, delta_x: u128) -> (PreciseNumber, bool) {
        let gil = Python::acquire_gil();
        let result: (u128, bool) = self
            .call1(gil.python(), "sim_delta_y_amm", (delta_x,))
            .unwrap()
            .extract(gil.python())
            .unwrap();
        let precise_number = PreciseNumber {
            value: InnerUint::from(result.0),
        };
        let is_signed = result.1;
        return (precise_number, is_signed);
    }

    pub fn sim_swap_x_to_y_amm(&self, delta_x: u128) -> (u128, u128, u128, u128) {
        let gil = Python::acquire_gil();
        return self
            .call1(gil.python(), "sim_swap_x_to_y_amm", (delta_x,))
            .unwrap()
            .extract(gil.python())
            .unwrap();
    }

    pub fn sim_delta_y_hmm(&self, delta_x: u128) -> (PreciseNumber, bool) {
        let gil = Python::acquire_gil();
        let result: (u128, bool) = self
            .call1(gil.python(), "sim_delta_y_hmm", (delta_x,))
            .unwrap()
            .extract(gil.python())
            .unwrap();
        let precise_number = PreciseNumber {
            value: InnerUint::from(result.0),
        };
        let is_signed = result.1;
        return (precise_number, is_signed);
    }

    pub fn sim_delta_x_hmm(&self, delta_y: u128) -> (PreciseNumber, bool) {
        let gil = Python::acquire_gil();
        let result: (u128, bool) = self
            .call1(gil.python(), "sim_delta_x_hmm", (delta_y,))
            .unwrap()
            .extract(gil.python())
            .unwrap();
        let precise_number = PreciseNumber {
            value: InnerUint::from(result.0),
        };
        let is_signed = result.1;
        return (precise_number, is_signed);
    }

    fn call0(&self, py: Python, method_name: &str) -> Result<PyObject, PyErr> {
        let sim = PyModule::from_code(py, &self.py_src, FILE_NAME, MODULE_NAME).unwrap();
        let model = sim
            .call1(
                "Curve",
                (self.x0, self.y0, self.c_numer, self.c_denom, self.i),
            )
            .unwrap()
            .to_object(py);
        let py_ret = model.as_ref(py).call_method0(method_name);
        self.extract_py_ret(py, py_ret)
    }

    fn call1(
        &self,
        py: Python,
        method_name: &str,
        args: impl IntoPy<Py<PyTuple>>,
    ) -> Result<PyObject, PyErr> {
        let sim = PyModule::from_code(py, &self.py_src, FILE_NAME, MODULE_NAME).unwrap();
        let model = sim
            .call1(
                "Curve",
                (self.x0, self.y0, self.c_numer, self.c_denom, self.i),
            )
            .unwrap()
            .to_object(py);
        let py_ret = model.as_ref(py).call_method1(method_name, args);
        self.extract_py_ret(py, py_ret)
    }

    fn extract_py_ret(&self, py: Python, ret: PyResult<&PyAny>) -> Result<PyObject, PyErr> {
        match ret {
            Ok(v) => v.extract(),
            Err(e) => {
                e.print_and_set_sys_last_vars(py);
                panic!("Python execution failed.")
            }
        }
    }

    pub fn print_src(&self) {
        println!("{}", self.py_src);
    }
}
